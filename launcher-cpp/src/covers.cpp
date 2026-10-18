#include "covers.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUrl>

#include "app_config.h"

namespace {

// UA « navigateur » : Cloudflare refuse les UA exotiques (comme la version Python).
const char *USER_AGENT =
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0 KirbyRetroLauncher/1.5";

}  // namespace

CoverLoader::CoverLoader(const QString &siteUrl, const QString &romsDir, QObject *parent)
    : QObject(parent), m_net(new QNetworkAccessManager(this)) {
    updateConfig(siteUrl, romsDir);
}

void CoverLoader::updateConfig(const QString &siteUrl, const QString &romsDir) {
    m_site = siteUrl.trimmed();
    while (m_site.endsWith(QLatin1Char('/'))) {
        m_site.chop(1);
    }
    m_roms = romsDir.trimmed();
}

QPixmap CoverLoader::cover(const QString &system, const QString &file, const QString &coverUrl) {
    const QString local = localPath(system, file);
    if (!local.isEmpty()) {
        return QPixmap(local);
    }
    const QString cached = cachePath(system, file);
    if (QFileInfo(cached).isFile()) {
        return QPixmap(cached);
    }
    const QString key = system + QLatin1Char('/') + file;
    if (!coverUrl.isEmpty() && !m_site.isEmpty() && !m_inflight.contains(key)) {
        m_inflight.insert(key);
        download(key, system, file, coverUrl);
    }
    return {};
}

QString CoverLoader::localPath(const QString &system, const QString &file) const {
    if (m_roms.isEmpty()) {
        return {};
    }
    const QDir root(m_roms);
    const QString stem = QFileInfo(file).completeBaseName();
    const QStringList candidates = {
        root.filePath(QStringLiteral("covers/") + system + QLatin1Char('/') + stem + ".png"),
        root.filePath(QStringLiteral("covers/") + system + QLatin1Char('/') + file + ".png"),
        root.filePath(system + "/covers/" + stem + ".png"),
        root.filePath(system + QLatin1Char('/') + stem + ".png"),
        root.filePath(system + QLatin1Char('/') + file + ".png"),
    };
    for (const QString &candidate : candidates) {
        if (QFileInfo(candidate).isFile()) {
            return candidate;
        }
    }
    return {};
}

QString CoverLoader::cachePath(const QString &system, const QString &file) const {
    return cacheDir() + "/covers/" + system + QLatin1Char('/') +
           QFileInfo(file).completeBaseName() + QStringLiteral(".png");
}

void CoverLoader::download(const QString &key, const QString &system, const QString &file,
                           const QString &url) {
    QString full = url;
    if (!full.startsWith(QStringLiteral("http://")) && !full.startsWith(QStringLiteral("https://"))) {
        if (!full.startsWith(QLatin1Char('/'))) {
            full.prepend(QLatin1Char('/'));
        }
        full.prepend(m_site);
    }
    QNetworkRequest request{QUrl(full, QUrl::TolerantMode)};
    request.setHeader(QNetworkRequest::UserAgentHeader, QString::fromLatin1(USER_AGENT));
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    QNetworkReply *reply = m_net->get(request);
    connect(reply, &QNetworkReply::finished, this, [this, reply, key, system, file]() {
        reply->deleteLater();
        m_inflight.remove(key);
        if (reply->error() != QNetworkReply::NoError) {
            return;
        }
        const QByteArray data = reply->readAll();
        if (data.size() <= 100) {
            return;
        }
        const QString dest = cachePath(system, file);
        QDir().mkpath(QFileInfo(dest).absolutePath());
        QFile out(dest);
        if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            return;
        }
        out.write(data);
        out.close();
        const QPixmap pixmap(dest);
        if (!pixmap.isNull()) {
            emit coverReady(key, pixmap);
        }
    });
}
