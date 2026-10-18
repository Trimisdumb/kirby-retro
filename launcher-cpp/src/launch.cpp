#include "launch.h"

#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QObject>
#include <QProcess>
#include <QStringList>

#include "detect.h"

namespace {

bool tryStart(const QStringList &command, const QString &workingDir, QString *error) {
    if (command.isEmpty() || command.first().isEmpty()) {
        *error = QObject::tr("Commande d'émulateur vide.");
        return false;
    }
    if (!QProcess::startDetached(command.first(), command.mid(1), workingDir)) {
        *error = QObject::tr("Impossible de lancer :\n%1").arg(command.join(QLatin1Char(' ')));
        return false;
    }
    return true;
}

LaunchOutcome tryNative(const QJsonObject &config, const QString &system, const QString &romPath) {
    LaunchOutcome outcome;
    const QJsonObject entry = config.value("emulators").toObject().value(system).toObject();
    const QString path = entry.value("path").toString().trimmed();
    if (path.isEmpty() || !QFileInfo(path).isFile()) {
        return outcome;  // pas d'émulateur natif configuré pour cette console
    }
    QStringList args;
    const QJsonArray configured = entry.value("args").toArray();
    for (const QJsonValue &value : configured) {
        args << value.toString()
                    .replace(QStringLiteral("{rom}"), romPath)
                    .replace(QStringLiteral("{rom_dir}"), QFileInfo(romPath).absolutePath());
    }
    if (args.isEmpty()) {
        args << romPath;
    }
    QString error;
    if (tryStart(QStringList{path} + args, QString(), &error)) {
        outcome.ok = true;
        outcome.message = QObject::tr("Lancé dans %1").arg(QFileInfo(path).fileName());
    } else {
        outcome.message = error;
    }
    return outcome;
}

LaunchOutcome tryRetroarch(const QJsonObject &config, const QString &system, const QString &romPath) {
    LaunchOutcome outcome;
    const QJsonObject retroarch = config.value("retroarch").toObject();
    const QString retroarchPath = retroarch.value("path").toString().trimmed();
    if (!retroarchOk(retroarchPath)) {
        return outcome;  // RetroArch introuvable → essayer l'autre stratégie
    }
    const QString core = resolveCorePath(retroarch.value("cores_dir").toString(), system);
    if (core.isEmpty()) {
        QStringList listing;
        for (const QString &dir : coresDirs(retroarchPath)) {
            listing << QStringLiteral("  · ") + dir;
        }
        outcome.message =
            QObject::tr("Core RetroArch introuvable pour « %1 ».\n"
                        "Core attendu : %2\n"
                        "Dossiers consultés :\n%3\n\n"
                        "Ouvre RetroArch → « Mise à jour en ligne » → « Gestionnaire de cœurs », "
                        "installe-le puis relance.")
                .arg(system, coreNamesFor(system),
                     listing.isEmpty() ? QObject::tr("  (aucun dossier de cores trouvé)")
                                       : listing.join(QLatin1Char('\n')));
        return outcome;
    }
    QStringList command = retroarchCommand(retroarchPath);
    command << QStringLiteral("-L") << core << romPath;
    const QString workingDir =
        isFlatpak(retroarchPath) ? QString() : QFileInfo(retroarchPath).absolutePath();
    QString error;
    if (tryStart(command, workingDir, &error)) {
        outcome.ok = true;
        outcome.message =
            QObject::tr("Lancé dans RetroArch (core %1)").arg(QFileInfo(core).baseName());
    } else {
        outcome.message = error;
    }
    return outcome;
}

}  // namespace

LaunchOutcome launchGame(const QJsonObject &config, const QString &system, const QString &romPath) {
    bool preferNative = false;
    for (const QJsonValue &value : config.value("prefer_native_for").toArray()) {
        if (value.toString() == system) {
            preferNative = true;
            break;
        }
    }

    QStringList errors;
    LaunchOutcome first = preferNative ? tryNative(config, system, romPath)
                                       : tryRetroarch(config, system, romPath);
    if (first.ok) {
        return first;
    }
    if (!first.message.isEmpty()) {
        errors << first.message;
    }
    LaunchOutcome second = preferNative ? tryRetroarch(config, system, romPath)
                                        : tryNative(config, system, romPath);
    if (second.ok) {
        return second;
    }
    if (!second.message.isEmpty()) {
        errors << second.message;
    }

    LaunchOutcome failure;
    failure.message =
        errors.isEmpty()
            ? QObject::tr("Aucun émulateur disponible.\n\nInstalle RetroArch ou configure un "
                          "émulateur natif dans Paramètres (dossier de cores inclus), puis réessaie.")
            : errors.join(QStringLiteral("\n\n"));
    return failure;
}
