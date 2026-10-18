#pragma once

#include <QHash>
#include <QString>
#include <QStringList>

// Console (id API) → cores RetroArch acceptables, par ordre de préférence.
extern const QHash<QString, QStringList> RETROARCH_CORES;

// Console → émulateurs standalone connus (cherchés dans le PATH).
extern const QHash<QString, QStringList> NATIVE_HINTS;

bool isFlatpak(const QString &retroarchPath);
bool retroarchOk(const QString &retroarchPath);
QString findRetroarch();
QString defaultCoresDir(const QString &retroarchPath);
QStringList coresDirs(const QString &retroarchPath);
QString resolveCorePath(const QString &coresDir, const QString &systemId);
QString coreNamesFor(const QString &systemId);
QString findNative(const QString &systemId);
QStringList retroarchCommand(const QString &retroarchPath);
