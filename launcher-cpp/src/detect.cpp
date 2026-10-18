#include "detect.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QObject>
#include <QProcess>
#include <QStandardPaths>
#include <QTextStream>

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

QString cfgLibretroDirectoryIn(const QString &cfgPath) {
    QFile file(cfgPath);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return {};
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
        if (value.length() >= 2 && value.startsWith(QLatin1Char('"')) && value.endsWith(QLatin1Char('"'))) {
            value = value.mid(1, value.length() - 2);
        }
        if (value.startsWith(QStringLiteral("~/"))) {
            value = homeDir() + value.mid(1);
        }
        const QFileInfo info(value);
        if (info.isDir()) {
            return info.absoluteFilePath();
        }
    }
    return {};
}

QString cfgLibretroDirectory() {
    const QString home = homeDir();
    const QStringList candidates = {
        home + "/.config/retroarch/retroarch.cfg",
        home + "/.retroarch/retroarch.cfg",
        home + "/.var/app/" + FLATPAK_ID + "/config/retroarch/retroarch.cfg",
        home + "/snap/retroarch/current/.config/retroarch/retroarch.cfg",
    };
    for (const QString &path : candidates) {
        const QString found = cfgLibretroDirectoryIn(path);
        if (!found.isEmpty()) {
            return found;
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

bool retroarchOk(const QString &retroarchPath) {
    const QString value = retroarchPath.trimmed();
    if (value.isEmpty()) {
        return false;
    }
    if (isFlatpak(value)) {
        return !QStandardPaths::findExecutable(QStringLiteral("flatpak")).isEmpty();
    }
    return QFileInfo(value).isFile();
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
    const QString programFiles = qEnvironmentVariable("ProgramFiles");
    const QString localAppData = qEnvironmentVariable("LOCALAPPDATA");
    candidates << programFiles + "/RetroArch/retroarch.exe"
               << programFiles + "/RetroArch-Win64/retroarch.exe"
               << localAppData + "/Programs/RetroArch/retroarch.exe";
#endif
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
    } else if (!retroarchPath.isEmpty() && QFileInfo(retroarchPath).isFile()) {
        dirs << QFileInfo(retroarchPath).absolutePath() + "/cores";
    }
    const QString cfgDir = cfgLibretroDirectory();
    if (!cfgDir.isEmpty()) {
        dirs << cfgDir;
    }
#ifdef Q_OS_WIN
    dirs << qEnvironmentVariable("APPDATA") + "/RetroArch/cores";
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
