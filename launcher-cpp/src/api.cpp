#include "api.h"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUrl>

namespace {

const char *USER_AGENT = "KirbyRetroLauncher/1.0";

QNetworkRequest jsonRequest(const QString &url) {
    QNetworkRequest request{QUrl(url)};
    request.setHeader(QNetworkRequest::UserAgentHeader, QString::fromLatin1(USER_AGENT));
    request.setRawHeader("Accept", "application/json");
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    return request;
}

}  // namespace

QString romUrl(const QString &siteUrl, const QString &system, const QString &file) {
    QString base = siteUrl;
    while (base.endsWith('/')) {
        base.chop(1);
    }
    return base + "/roms/" + QString::fromLatin1(QUrl::toPercentEncoding(system)) + "/" +
           QString::fromLatin1(QUrl::toPercentEncoding(file));
}

Api::Api(QObject *parent) : QObject(parent), m_net(new QNetworkAccessManager(this)) {}

void Api::fetchLibrary(const QString &siteUrl) {
    QString base = siteUrl;
    while (base.endsWith('/')) {
        base.chop(1);
    }
    QNetworkReply *reply = m_net->get(jsonRequest(base + "/api/library"));
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        if (reply->error() != QNetworkReply::NoError) {
            emit failed(reply->errorString());
            return;
        }
        QJsonParseError parseError{};
        const QJsonDocument doc = QJsonDocument::fromJson(reply->readAll(), &parseError);
        if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
            emit failed(tr("Réponse illisible du site (%1).").arg(parseError.errorString()));
            return;
        }

        const QJsonObject root = doc.object();
        Library library;
        library.name = root.value("name").toString();
        library.totalGames = root.value("totalGames").toInt();

        for (const QJsonValue &systemValue : root.value("systems").toArray()) {
            const QJsonObject systemObject = systemValue.toObject();
            SystemInfo system;
            system.id = systemObject.value("id").toString();
            system.label = systemObject.value("label").toString();
            for (const QJsonValue &gameValue : systemObject.value("games").toArray()) {
                const QJsonObject gameObject = gameValue.toObject();
                Game game;
                game.system = gameObject.value("system").toString(system.id);
                game.file = gameObject.value("file").toString();
                game.title = gameObject.value("title").toString();
                game.region = gameObject.value("region").toString();
                game.cover = gameObject.value("cover").toString();
                game.coverSource = gameObject.value("coverSource").toString();
                game.year = static_cast<int>(gameObject.value("year").toDouble());
                game.size = static_cast<qint64>(gameObject.value("size").toDouble());
                system.games.append(game);
            }
            if (!system.id.isEmpty() || !system.games.isEmpty()) {
                library.systems.append(system);
            }
        }
        emit ready(library);
    });
}

QNetworkReply *Api::downloadRom(const QString &siteUrl, const QString &system,
                                const QString &file, QFile *out) {
    QNetworkRequest request{QUrl(romUrl(siteUrl, system, file))};
    request.setHeader(QNetworkRequest::UserAgentHeader, QString::fromLatin1(USER_AGENT));
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    QNetworkReply *reply = m_net->get(request);
    connect(reply, &QIODevice::readyRead, out, [reply, out]() {
        out->write(reply->readAll());
    });
    return reply;
}
