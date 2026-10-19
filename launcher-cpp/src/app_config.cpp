#include "app_config.h"

#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QStandardPaths>

#include "detect.h"

namespace {

const char *APP_NAME = "KirbyRetroLauncher";

QJsonObject mergeObjects(QJsonObject base, const QJsonObject &overlay) {
    // Fusion douce : les clés inconnues du fichier sont conservées (compatibilité
    // avec la version Python, qui peut en écrire d'autres).
    for (auto it = overlay.begin(); it != overlay.end(); ++it) {
        if (base.contains(it.key()) && base.value(it.key()).isObject() && it.value().isObject()) {
            base[it.key()] = mergeObjects(base.value(it.key()).toObject(), it.value().toObject());
        } else {
            base[it.key()] = it.value();
        }
    }
    return base;
}

}  // namespace

QString configDir() {
#ifdef Q_OS_WIN
    const QString base = qEnvironmentVariable("APPDATA", QDir::homePath() + "/AppData/Roaming");
#else
    const QString base = qEnvironmentVariable("XDG_CONFIG_HOME", QDir::homePath() + "/.config");
#endif
    const QString path = base + "/" + APP_NAME;
    QDir().mkpath(path);
    return path;
}

QString configPath() {
    return configDir() + "/config.json";
}

QString cacheDir() {
#ifdef Q_OS_WIN
    const QString base = qEnvironmentVariable("LOCALAPPDATA", QDir::homePath() + "/AppData/Local");
#else
    const QString base = qEnvironmentVariable("XDG_CACHE_HOME", QDir::homePath() + "/.cache");
#endif
    const QString path = base + "/" + APP_NAME;
    QDir().mkpath(path);
    return path;
}

QJsonObject defaultConfig() {
    QJsonObject retroarch;
    retroarch["path"] = "";
    retroarch["cores_dir"] = "";

    QJsonObject netplay;
    netplay["nickname"] = "";
    netplay["port"] = 55435;
    netplay["last_host"] = "";
    netplay["use_relay"] = false;

    QJsonArray prefer;
    prefer.append("nds");
    prefer.append("n64");
    prefer.append("psx");

    QJsonObject config;
    config["site_url"] = "https://retro.kirbytrim.buzz";
    config["roms_dir"] = "";
    config["download_missing_roms"] = true;
    config["auto_sync_saves"] = true;
    config["retroarch"] = retroarch;
    config["emulators"] = QJsonObject();
    config["prefer_native_for"] = prefer;
    config["netplay"] = netplay;
    return config;
}

QJsonObject loadConfig() {
    QJsonObject config = defaultConfig();
    QFile file(configPath());
    if (!file.open(QIODevice::ReadOnly)) {
        return config;
    }
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isObject()) {
        return config;
    }
    return mergeObjects(config, doc.object());
}

void saveConfig(const QJsonObject &config) {
    QFile file(configPath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        return;
    }
    file.write(QJsonDocument(config).toJson(QJsonDocument::Indented));
}

void autofill(QJsonObject &config) {
    if (config.value("roms_dir").toString().trimmed().isEmpty()) {
        config["roms_dir"] = QDir::homePath() + "/KirbyRetroROMs";
    }

    QJsonObject retroarch = config.value("retroarch").toObject();
    // Chemin noté mais devenu invalide (RetroArch déplacé, désinstallé…) :
    // on redétecte plutôt que d'échouer au lancement.
    if (!retroarch.value("path").toString().isEmpty() &&
        retroarchExecutable(retroarch.value("path").toString()).isEmpty()) {
        retroarch["path"] = QString();
    }
    if (retroarch.value("path").toString().isEmpty()) {
        const QString found = findRetroarch();
        if (!found.isEmpty()) {
            retroarch["path"] = found;
        }
    } else {
        // Un dossier saisi à la main → on garde le chemin de l'exécutable.
        const QString exe = retroarchExecutable(retroarch.value("path").toString());
        if (!exe.isEmpty() && !isFlatpak(exe)) {
            retroarch["path"] = exe;
        }
    }
    if (retroarch.value("cores_dir").toString().isEmpty() ||
        !QDir(retroarch.value("cores_dir").toString()).exists()) {
        const QString cores = defaultCoresDir(retroarch.value("path").toString());
        if (!cores.isEmpty()) {
            retroarch["cores_dir"] = cores;
        }
    }
    config["retroarch"] = retroarch;

    QJsonObject emulators = config.value("emulators").toObject();
    for (auto it = NATIVE_HINTS.constBegin(); it != NATIVE_HINTS.constEnd(); ++it) {
        QJsonObject entry = emulators.value(it.key()).toObject();
        if (entry.value("path").toString().isEmpty()) {
            const QString native = findNative(it.key());
            if (!native.isEmpty()) {
                entry["path"] = native;
                if (!entry.contains("args")) {
                    QJsonArray args;
                    args.append("{rom}");
                    entry["args"] = args;
                }
            }
        }
        emulators[it.key()] = entry;
    }
    config["emulators"] = emulators;
}
