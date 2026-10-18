#pragma once

#include <QJsonObject>
#include <QString>

struct LaunchOutcome {
    bool ok = false;
    QString message;  // note affichée en cas de succès, sinon l'erreur
};

// Lance le jeu : émulateur natif d'abord si la console est dans
// `prefer_native_for`, sinon RetroArch d'abord (même stratégie que la
// version Python).
LaunchOutcome launchGame(const QJsonObject &config, const QString &system,
                         const QString &romPath);
