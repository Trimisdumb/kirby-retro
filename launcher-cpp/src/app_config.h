#pragma once

#include <QJsonObject>
#include <QString>

// Emplacements des fichiers — mêmes chemins que la version Python pour que
// les deux launchers partagent configuration et cache.
QString configDir();
QString configPath();
QString cacheDir();

QJsonObject defaultConfig();
QJsonObject loadConfig();
void saveConfig(const QJsonObject &config);

// Complète RetroArch / dossier de cores / émulateurs natifs s'ils sont vides.
void autofill(QJsonObject &config);
