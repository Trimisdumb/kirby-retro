#pragma once

#include <QList>
#include <QObject>
#include <QString>
#include <QtGlobal>

class QFile;
class QNetworkAccessManager;
class QNetworkReply;

// Un jeu tel que renvoyé par l'API du site.
struct Game {
    QString system;
    QString file;
    QString title;
    QString region;
    QString cover;
    QString coverSource;
    int year = 0;
    qint64 size = 0;
};

struct SystemInfo {
    QString id;
    QString label;
    QList<Game> games;
};

struct Library {
    QString name;
    int totalGames = 0;
    QList<SystemInfo> systems;
};

// Client HTTP vers l'API du site (mêmes endpoints que la version Python).
class Api : public QObject {
    Q_OBJECT

public:
    explicit Api(QObject *parent = nullptr);

    void fetchLibrary(const QString &siteUrl);

    // Télécharge une ROM vers `out` (le fichier doit être ouvert en écriture).
    // Le flux est recopié au fur et à mesure ; suivre downloadProgress sur le
    // QNetworkReply retourné.
    QNetworkReply *downloadRom(const QString &siteUrl, const QString &system,
                               const QString &file, QFile *out);

signals:
    void ready(const Library &library);
    void failed(const QString &error);

private:
    QNetworkAccessManager *m_net;
};

QString romUrl(const QString &siteUrl, const QString &system, const QString &file);
