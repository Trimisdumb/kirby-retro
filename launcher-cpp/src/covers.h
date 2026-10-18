#pragma once

#include <QObject>
#include <QPixmap>
#include <QSet>
#include <QString>

class QNetworkAccessManager;

// Charge les jaquettes : dossier ROMs, cache local, sinon téléchargement
// depuis le site (cache partagé avec la version Python).
class CoverLoader : public QObject {
    Q_OBJECT

public:
    CoverLoader(const QString &siteUrl, const QString &romsDir, QObject *parent = nullptr);
    void updateConfig(const QString &siteUrl, const QString &romsDir);

    // Renvoie la jaquette si elle est connue localement ; sinon déclenche le
    // téléchargement et émet coverReady plus tard (pixmap nulle en attendant).
    QPixmap cover(const QString &system, const QString &file, const QString &coverUrl);

signals:
    void coverReady(const QString &key, const QPixmap &pixmap);

private:
    QString localPath(const QString &system, const QString &file) const;
    QString cachePath(const QString &system, const QString &file) const;
    void download(const QString &key, const QString &system, const QString &file,
                  const QString &url);

    QNetworkAccessManager *m_net;
    QString m_site;
    QString m_roms;
    QSet<QString> m_inflight;
};
