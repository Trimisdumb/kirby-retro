#include "detect.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QObject>
#include <QProcess>
#include <QStandardPaths>
#include <QSysInfo>
#include <QTextStream>

#include "app_config.h"

const QHash<QString, QStringList> RETROARCH_CORES = {
    {"nes", {"fceumm_libretro", "mesen2_libretro", "nestopia_libretro", "mesen-s_libretro"}},
    {"snes", {"snes9x_libretro", "bsnes_libretro", "mesen-s_libretro"}},
    {"gb", {"gambatte_libretro", "sameboy_libretro", "gearboy_libretro"}},
    {"gba", {"mgba_libretro", "gpsp_libretro", "vba_next_libretro"}},
    {"n64", {"mupen64plus_next_libretro", "parallel_n64_libretro"}},
    {"nds", {"melondsds_libretro", "melonds_libretro", "desmume_libretro", "desmume2015_libretro"}},
    {"psx", {"pcsx_rearmed_libretro", "swanstation_libretro", "mednafen_psx_libretro", "mednafen_psx_hw_libretro"}},
    {"ps2", {"pcsx2_libretro"}},
    {"psp", {"ppsspp_libretro"}},
    {"segaMD", {"genesis_plus_gx_libretro", "picodrive_libretro"}},
    {"segaMS", {"genesis_plus_gx_libretro", "picodrive_libretro"}},
    {"segaGG", {"genesis_plus_gx_libretro", "picodrive_libretro"}},
    {"segaCD", {"genesis_plus_gx_libretro", "picodrive_libretro"}},
    {"sega32x", {"picodrive_libretro"}},
    {"segaSaturn", {"mednafen_saturn_libretro", "kronos_libretro", "yabause_libretro", "yabasanshiro_libretro"}},
    {"dreamcast", {"flycast_libretro"}},
    {"gamecube", {"dolphin_libretro"}},
    {"wii", {"dolphin_libretro"}},
    {"3ds", {"azahar_libretro", "citra2018_libretro", "citra_libretro"}},
    {"arcade", {"fbneo_libretro", "mame2003_plus_libretro", "mame2003_libretro", "fbalpha2012_libretro"}},
    {"pce", {"mednafen_pce_libretro", "mednafen_pce_fast_libretro", "mednafen_supergrafx_libretro"}},
    {"atari2600", {"stella2014_libretro", "stella_libretro"}},
    {"lynx", {"handy_libretro", "mednafen_lynx_libretro"}},
    {"c64", {"vice_x64sc_libretro", "vice_x64_libretro"}},
    {"vb", {"mednafen_vb_libretro", "beetle_vb_libretro"}},
    {"cpc", {"cap32_libretro", "crocods_libretro"}},
    {"apple2", {"applewin_libretro"}},
    {"pc88", {"quasi88_libretro"}},
    {"pokemini", {"pokemini_libretro"}},
};

const QHash<QString, QStringList> NATIVE_HINTS = {
    {"nds", {"melonDS", "melonds", "melonDS-DS"}},
    {"n64", {"simple64-gui", "parallel-launcher", "mupen64plus"}},
    {"psx", {"duckstation-qt", "duckstation"}},
    {"ps2", {"pcsx2-qt", "pcsx2"}},
    {"psp", {"ppsspp-qt", "ppsspp"}},
    {"segaSaturn", {"mednafen"}},
    {"dreamcast", {"flycast", "redream"}},
    {"gamecube", {"dolphin-emu", "dolphin"}},
    {"wii", {"dolphin-emu", "dolphin"}},
    {"snes", {"snes9x-gtk", "snes9x"}},
    {"nes", {"fceux", "mesen"}},
    {"gba", {"mgba-qt", "mgba"}},
    {"gb", {"sameboy", "mgba-qt"}},
    {"cpc", {"caprice32"}},
    {"pc88", {"quasi88"}},
};

namespace {

const char *FLATPAK_ID = "org.libretro.RetroArch";

QString homeDir() {
    return QDir::homePath();
}

QString flatpakCoresDir() {
    return homeDir() + "/.var/app/" + FLATPAK_ID + "/config/retroarch/cores";
}

bool flatpakInstalled() {
    if (QDir(QString("/var/lib/flatpak/app/") + FLATPAK_ID).exists() ||
        QDir(homeDir() + "/.local/share/flatpak/app/" + FLATPAK_ID).exists()) {
        return true;
    }
    if (QStandardPaths::findExecutable(QStringLiteral("flatpak")).isEmpty()) {
        return false;
    }
    QProcess process;
    process.start(QStringLiteral("flatpak"),
                  {QStringLiteral("info"), QString::fromLatin1(FLATPAK_ID)});
    if (!process.waitForFinished(20000)) {
        return false;
    }
    return process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0;
}

// Dossier de base de RetroArch (« C:/RetroArch-Win64 ») pour un chemin donné.
QString directoryOf(const QString &path) {
    const QFileInfo info(path.trimmed());
    return info.isDir() ? info.absoluteFilePath() : info.absolutePath();
}

// Remplace %APPDATA%, %LOCALAPPDATA%… et $HOME dans une valeur de retroarch.cfg.
QString expandVariables(QString value) {
    static const char *KEYS[] = {"APPDATA", "LOCALAPPDATA", "USERPROFILE", "ProgramFiles", "HOME"};
    for (const char *key : KEYS) {
        const QString variable = qEnvironmentVariable(key);
        if (variable.isEmpty()) {
            continue;
        }
        const QString name = QString::fromLatin1(key);
        value.replace(QLatin1Char('%') + name + QLatin1Char('%'), variable, Qt::CaseInsensitive);
        value.replace(QLatin1Char('$') + name, variable);
    }
    return value;
}

// Interprète une valeur de chemin de retroarch.cfg : « ~/… », « %APPDATA%\… »,
// « :/cores » (à côté de l'exécutable) ou chemin relatif — sans oublier « default ».
QString resolveCfgPath(const QString &raw, const QString &exeDir) {
    QString value = expandVariables(raw.trimmed());
    if (value.isEmpty() || value == QLatin1String("default") || value == QLatin1String(":") ||
        value == QLatin1String(":/")) {
        return {};
    }
    if (value.startsWith(QLatin1Char(':'))) {
        while (value.startsWith(QLatin1Char(':')) || value.startsWith(QLatin1Char('/'))) {
            value.remove(0, 1);
        }
        return exeDir.isEmpty() ? QString() : QDir(exeDir).filePath(value);
    }
    if (value.startsWith(QLatin1Char('~'))) {
        value = homeDir() + value.mid(1);
    }
    if (!value.isEmpty() && !QFileInfo(value).isAbsolute() && !exeDir.isEmpty()) {
        value = QDir(exeDir).filePath(value);
    }
    return QDir::cleanPath(value);
}

// Fichiers retroarch.cfg à consulter (ceux que RetroArch écrit sur chaque système).
QStringList cfgCandidates(const QString &retroarchPath) {
    const QString home = homeDir();
    QStringList paths;
    if (!retroarchPath.trimmed().isEmpty()) {
        paths << directoryOf(retroarchPath) + "/retroarch.cfg";
    }
    paths << home + "/.config/retroarch/retroarch.cfg"
          << home + "/.retroarch/retroarch.cfg"
          << home + "/.var/app/" + FLATPAK_ID + "/config/retroarch/retroarch.cfg"
          << home + "/snap/retroarch/current/.config/retroarch/retroarch.cfg";
#ifdef Q_OS_WIN
    const QString appData = qEnvironmentVariable("APPDATA");
    const QString localAppData = qEnvironmentVariable("LOCALAPPDATA");
    if (!appData.isEmpty()) {
        paths << appData + "/RetroArch/retroarch.cfg";
    }
    if (!localAppData.isEmpty()) {
        paths << localAppData + "/RetroArch/retroarch.cfg";
    }
#endif
    return paths;
}

// Dossier de cores déclaré par RetroArch lui-même (retroarch.cfg → libretro_directory).
QString cfgLibretroDirectory(const QString &retroarchPath) {
    const QString exeDir =
        retroarchPath.trimmed().isEmpty() ? QString() : directoryOf(retroarchPath);
    for (const QString &path : cfgCandidates(retroarchPath)) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
            continue;
        }
        QTextStream stream(&file);
        while (!stream.atEnd()) {
            const QString line = stream.readLine().trimmed();
            if (!line.startsWith(QStringLiteral("libretro_directory"))) {
                continue;
            }
            const int equal = line.indexOf(QLatin1Char('='));
            if (equal < 0) {
                continue;
            }
            QString value = line.mid(equal + 1).trimmed();
            if (value.length() >= 2 && value.startsWith(QLatin1Char('"')) &&
                value.endsWith(QLatin1Char('"'))) {
                value = value.mid(1, value.length() - 2);
            }
            const QString resolved = resolveCfgPath(value, exeDir);
            const QFileInfo info(resolved);
            if (!resolved.isEmpty() && info.isDir()) {
                return info.absoluteFilePath();
            }
        }
    }
    return {};
}

QString coreExtension() {
#if defined(Q_OS_WIN)
    return QStringLiteral(".dll");
#elif defined(Q_OS_MAC)
    return QStringLiteral(".dylib");
#else
    return QStringLiteral(".so");
#endif
}

}  // namespace

bool isFlatpak(const QString &retroarchPath) {
    return retroarchPath.trimmed().startsWith(QStringLiteral("flatpak"));
}

QString retroarchExecutable(const QString &path) {
    const QString value = path.trimmed();
    if (value.isEmpty()) {
        return {};
    }
    if (isFlatpak(value)) {
        return QStandardPaths::findExecutable(QStringLiteral("flatpak")).isEmpty() ? QString()
                                                                                  : value;
    }
    const QFileInfo info(value);
    if (info.isFile()) {
        return info.absoluteFilePath();
    }
    // Un dossier est accepté : l'utilisateur a pu choisir « C:\RetroArch-Win64 »
    // plutôt que retroarch.exe — on y cherche l'exécutable.
    if (info.isDir()) {
        const QStringList names = {
            QStringLiteral("retroarch.exe"),
            QStringLiteral("retroarch"),
            QStringLiteral("RetroArch.AppImage"),
        };
        for (const QString &name : names) {
            const QString candidate = QDir(info.absoluteFilePath()).filePath(name);
            if (QFileInfo(candidate).isFile()) {
                return candidate;
            }
        }
    }
    return {};
}

bool retroarchOk(const QString &retroarchPath) {
    return !retroarchExecutable(retroarchPath).isEmpty();
}

QString findRetroarch() {
    const QString found = QStandardPaths::findExecutable(QStringLiteral("retroarch"));
    if (!found.isEmpty()) {
        return found;
    }
    if (flatpakInstalled()) {
        return QStringLiteral("flatpak run ") + FLATPAK_ID;
    }
    const QString home = homeDir();
    QStringList candidates = {
        QStringLiteral("/usr/bin/retroarch"),
        QStringLiteral("/usr/local/bin/retroarch"),
        home + "/.local/bin/retroarch",
        home + "/Applications/RetroArch.AppImage",
        QStringLiteral("/snap/bin/retroarch"),
    };
#ifdef Q_OS_WIN
    // L'installateur officiel de retroarch.com se pose par défaut dans
    // « C:\RetroArch-Win64 » : on balaie les dossiers de base classiques, la
    // racine du disque C: et le voisinage du launcher (version portable).
    QStringList roots;
    for (const char *key : {"ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "USERPROFILE",
                            "APPDATA"}) {
        const QString value = qEnvironmentVariable(key);
        if (!value.isEmpty()) {
            roots << value;
        }
    }
    roots << home << QStringLiteral("C:/");
    const QStringList names = {
        QStringLiteral("RetroArch/retroarch.exe"),
        QStringLiteral("RetroArch-Win64/retroarch.exe"),
        QStringLiteral("Steam/steamapps/common/RetroArch/retroarch.exe"),
        QStringLiteral("Programs/RetroArch/retroarch.exe"),
    };
    for (const QString &root : roots) {
        for (const QString &name : names) {
            candidates << root + QLatin1Char('/') + name;
        }
    }
    if (QCoreApplication::instance()) {
        const QString beside = QCoreApplication::applicationDirPath();
        candidates << beside + "/retroarch/retroarch.exe" << beside + "/retroarch.exe";
    }
#endif
    // Affichage et lancement avec les séparateurs du système (Windows : « \ »).
    for (QString &path : candidates) {
        path = QDir::toNativeSeparators(path);
    }
    for (const QString &path : candidates) {
        if (QFileInfo(path).isFile()) {
            return path;
        }
    }
    return {};
}

QStringList coresDirs(const QString &retroarchPath) {
    const QString home = homeDir();
    QStringList dirs;
    if (isFlatpak(retroarchPath)) {
        dirs << flatpakCoresDir();
    } else if (!retroarchPath.trimmed().isEmpty()) {
        // À côté de l'exécutable : standard portable (Windows inclus).
        dirs << directoryOf(retroarchPath) + "/cores";
    }
    const QString cfgDir = cfgLibretroDirectory(retroarchPath);
    if (!cfgDir.isEmpty()) {
        dirs << cfgDir;
    }
#ifdef Q_OS_WIN
    for (const char *key : {"APPDATA", "LOCALAPPDATA"}) {
        const QString value = qEnvironmentVariable(key);
        if (!value.isEmpty()) {
            dirs << value + "/RetroArch/cores";
        }
    }
#else
    dirs << home + "/.config/retroarch/cores"
         << home + "/.retroarch/cores"
         << home + "/snap/retroarch/current/.config/retroarch/cores"
         << QStringLiteral("/snap/retroarch/current/usr/lib/libretro")
         << QStringLiteral("/usr/lib/libretro")
         << QStringLiteral("/usr/lib64/libretro")
         << QStringLiteral("/usr/lib/x86_64-linux-gnu/libretro")
         << QStringLiteral("/usr/share/libretro/cores")
         << flatpakCoresDir();
#endif
    QStringList existing;
    for (const QString &dir : dirs) {
        if (!existing.contains(dir) && QDir(dir).exists()) {
            existing << dir;
        }
    }
    return existing;
}

QString defaultCoresDir(const QString &retroarchPath) {
    const QStringList dirs = coresDirs(retroarchPath);
    return dirs.isEmpty() ? QString() : dirs.first();
}

QString resolveCorePath(const QString &coresDir, const QString &systemId) {
    const QStringList names = RETROARCH_CORES.value(systemId);
    if (names.isEmpty()) {
        return {};
    }
    QStringList search;
    if (!coresDir.trimmed().isEmpty()) {
        const QDir dir(coresDir.trimmed());
        if (dir.exists()) {
            search << dir.absolutePath();
        }
    }
    for (const QString &dir : coresDirs(QString())) {
        if (!search.contains(dir)) {
            search << dir;
        }
    }
    const QString extension = coreExtension();
    for (const QString &name : names) {
        for (const QString &base : search) {
            const QStringList candidates = {
                base + "/" + name + extension,
                base + "/" + name + ".so",
                base + "/" + name + ".dll",
            };
            for (const QString &candidate : candidates) {
                if (QFileInfo(candidate).isFile()) {
                    return candidate;
                }
            }
        }
    }
    // Correspondance approximative : « melondsds_libretro.so » pour « melonds ».
    for (const QString &name : names) {
        const QString stem = QString(name).remove(QStringLiteral("_libretro")).toLower();
        for (const QString &base : search) {
            const QDir dir(base);
            const QStringList files = dir.entryList(QDir::Files, QDir::Name);
            for (const QString &file : files) {
                const QString lower = file.toLower();
                if (lower.contains(stem) && lower.contains(QStringLiteral("libretro"))) {
                    return dir.absoluteFilePath(file);
                }
            }
        }
    }
    return {};
}

QString coreNamesFor(const QString &systemId) {
    const QStringList names = RETROARCH_CORES.value(systemId);
    return names.isEmpty() ? QStringLiteral("?") : names.join(QStringLiteral(" / "));
}

QString findNative(const QString &systemId) {
    for (const QString &name : NATIVE_HINTS.value(systemId)) {
        const QString found = QStandardPaths::findExecutable(name);
        if (!found.isEmpty()) {
            return found;
        }
    }
    return {};
}

QStringList retroarchCommand(const QString &retroarchPath) {
    if (isFlatpak(retroarchPath)) {
        return {QStringLiteral("flatpak"), QStringLiteral("run"),
                QString::fromLatin1(FLATPAK_ID)};
    }
    return {retroarchPath};
}

QString diagnosticReport(const QJsonObject &config) {
    const QJsonObject retroarch = config.value("retroarch").toObject();
    const QString configured = retroarch.value("path").toString().trimmed();
    const QString coresConfigured = retroarch.value("cores_dir").toString().trimmed();
    const QString exe = retroarchExecutable(configured);
    const QString detected = findRetroarch();
    // Chemins affichés avec les séparateurs du système (Windows : « \ »).
    const auto native = [](const QString &path) { return QDir::toNativeSeparators(path); };

    QStringList lines;
    lines << QStringLiteral("Kirby Retro Launcher — diagnostic");
#ifdef KIRBY_VERSION
    lines << QStringLiteral("Version : ") + QString::fromLatin1(KIRBY_VERSION);
#endif
    lines << QStringLiteral("Système : ") + QSysInfo::prettyProductName() + QStringLiteral(" (") +
                 QSysInfo::currentCpuArchitecture() + QLatin1Char(')');
    lines << QStringLiteral("Configuration : ") + native(configPath());
    lines << QStringLiteral("Site : ") + config.value("site_url").toString();
    lines << QStringLiteral("Dossier ROMs : ") + native(config.value("roms_dir").toString());
    lines << QString();

    lines << QStringLiteral("RetroArch choisi : ") +
                 (exe.isEmpty() ? QStringLiteral("introuvable — à corriger dans Paramètres (valeur : ") +
                                      native(configured) + QStringLiteral(")")
                                : native(exe));
    lines << QStringLiteral("Détecté automatiquement : ") +
                 (detected.isEmpty() ? QStringLiteral("(rien trouvé)") : native(detected));
    lines << QString();

    const QStringList dirs = coresDirs(exe.isEmpty() ? configured : exe);
    lines << QStringLiteral("Dossiers de cores :");
    if (dirs.isEmpty()) {
        lines << QStringLiteral("  · (aucun dossier trouvé)");
    }
    for (const QString &dir : dirs) {
        lines << QStringLiteral("  · ") + native(dir);
    }
    if (!coresConfigured.isEmpty()) {
        lines << QStringLiteral("Dossier choisi à la main : ") + native(coresConfigured) +
                     (QDir(coresConfigured).exists() ? QStringLiteral(" (ok)")
                                                     : QStringLiteral(" (introuvable)"));
    }
    lines << QString();

    lines << QStringLiteral("Cores par console :");
    QStringList systems = RETROARCH_CORES.keys();
    systems.sort();
    for (const QString &system : systems) {
        const QString core = resolveCorePath(coresConfigured, system);
        lines << QStringLiteral("  · ") + system + QStringLiteral(" : ") +
                     (core.isEmpty() ? QStringLiteral("(absent)") : QFileInfo(core).fileName());
    }
    lines << QString();

    const QJsonObject emulators = config.value("emulators").toObject();
    QStringList nativeSystems = NATIVE_HINTS.keys();
    nativeSystems.sort();
    QStringList nativeLines;
    for (const QString &system : nativeSystems) {
        const QString chosen = emulators.value(system).toObject().value("path").toString();
        const QString found = findNative(system);
        if (chosen.isEmpty() && found.isEmpty()) {
            continue;
        }
        nativeLines << QStringLiteral("  · ") + system + QStringLiteral(" : ") +
                           (chosen.isEmpty() ? QStringLiteral("(non configuré)") : chosen) +
                           (found.isEmpty() ? QString()
                                            : QStringLiteral(" — détecté : ") + found);
    }
    lines << QStringLiteral("Émulateurs natifs :");
    lines << (nativeLines.isEmpty() ? QStringLiteral("  · (aucun)") : nativeLines.join(QLatin1Char('\n')));
    lines << QString();
    lines << QStringLiteral("Configuration complète :");
    lines << QString::fromUtf8(QJsonDocument(config).toJson(QJsonDocument::Indented)).trimmed();
    return lines.join(QLatin1Char('\n'));
}
