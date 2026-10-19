#include "mainwindow.h"

#include <QAction>
#include <QApplication>
#include <QClipboard>
#include <QComboBox>
#include <QDialog>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QIcon>
#include <QLabel>
#include <QLineEdit>
#include <QMenu>
#include <QMenuBar>
#include <QMessageBox>
#include <QNetworkReply>
#include <QPlainTextEdit>
#include <QProgressDialog>
#include <QPushButton>
#include <QStatusBar>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTimer>
#include <QToolBar>
#include <QVBoxLayout>

#include "app_config.h"
#include "covers.h"
#include "detect.h"
#include "launch.h"
#include "settingsdialog.h"

namespace {

// Rôles des données stockées sur la colonne « Bannière » de chaque ligne.
constexpr int SysRole = Qt::UserRole + 1;
constexpr int FileRole = Qt::UserRole + 2;
constexpr int NormRole = Qt::UserRole + 3;

// Minuscules sans accents pour la recherche.
QString normalize(const QString &text) {
    const QString decomposed = text.normalized(QString::NormalizationForm_D).toLower();
    QString out;
    out.reserve(decomposed.size());
    for (const QChar &character : decomposed) {
        if (character.category() != QChar::Mark_NonSpacing) {
            out += character;
        }
    }
    return out;
}

QString humanSize(qint64 bytes) {
    constexpr double KILO = 1024.0;
    constexpr double MEGA = KILO * 1024.0;
    constexpr double GIGA = MEGA * 1024.0;
    if (bytes <= 0) {
        return {};
    }
    if (bytes < KILO) {
        return QString::number(bytes) + QObject::tr(" o");
    }
    if (bytes < MEGA) {
        return QString::number(qRound64(bytes / KILO)) + QObject::tr(" Kio");
    }
    if (bytes < GIGA) {
        return QString::number(bytes / MEGA, 'f', 1) + QObject::tr(" Mio");
    }
    return QString::number(bytes / GIGA, 'f', 2) + QObject::tr(" Gio");
}

QPixmap scaleCover(const QPixmap &pixmap) {
    return pixmap.scaled(QSize(64, 46), Qt::KeepAspectRatio, Qt::SmoothTransformation);
}

// Cellule qui se trie sur la valeur numérique stockée dans Qt::UserRole.
class NumericItem : public QTableWidgetItem {
public:
    using QTableWidgetItem::QTableWidgetItem;

    bool operator<(const QTableWidgetItem &other) const override {
        return data(Qt::UserRole).toLongLong() < other.data(Qt::UserRole).toLongLong();
    }
};

}  // namespace

MainWindow::MainWindow() {
    setWindowTitle(QStringLiteral("Kirby Retro Launcher"));
    resize(1180, 760);

    m_config = loadConfig();
    autofill(m_config);
    m_api = new Api(this);
    m_covers = new CoverLoader(m_config.value("site_url").toString(),
                               m_config.value("roms_dir").toString(), this);

    buildMenus();
    buildToolbar();
    buildTable();

    m_countLabel = new QLabel(this);
    statusBar()->addPermanentWidget(m_countLabel);

    connect(m_api, &Api::ready, this, &MainWindow::onLibraryReady);
    connect(m_api, &Api::failed, this, &MainWindow::onLibraryFailed);
    connect(m_covers, &CoverLoader::coverReady, this,
            [this](const QString &key, const QPixmap &pixmap) {
                const int slash = key.indexOf(QLatin1Char('/'));
                if (slash > 0) {
                    setCover(key.left(slash), key.mid(slash + 1), pixmap);
                }
            });

    setStatus(tr("Chargement du catalogue…"));
    QTimer::singleShot(150, this, &MainWindow::refreshLibrary);
}

void MainWindow::buildMenus() {
    QMenu *fileMenu = menuBar()->addMenu(tr("&Fichier"));
    QAction *quit = fileMenu->addAction(tr("Quitter"));
    quit->setShortcut(QKeySequence::Quit);
    connect(quit, &QAction::triggered, this, &QWidget::close);

    QMenu *emulationMenu = menuBar()->addMenu(tr("&Émulation"));
    QAction *play = emulationMenu->addAction(tr("Démarrer"));
    connect(play, &QAction::triggered, this, &MainWindow::playSelected);

    QMenu *optionsMenu = menuBar()->addMenu(tr("&Options"));
    QAction *settings = optionsMenu->addAction(tr("Paramètres…"));
    connect(settings, &QAction::triggered, this, &MainWindow::openSettings);

    QMenu *helpMenu = menuBar()->addMenu(tr("&Aide"));
    QAction *diagnostic = helpMenu->addAction(tr("Diagnostic…"));
    connect(diagnostic, &QAction::triggered, this, &MainWindow::showDiagnostic);
    QAction *about = helpMenu->addAction(tr("À propos"));
    connect(about, &QAction::triggered, this, [this]() {
        QMessageBox::about(this, tr("À propos"),
                           tr("<b>Kirby Retro Launcher</b> — version %1 (C++ / Qt %2)<br>"
                              "%3 jeux dans la bibliothèque.<br><br>"
                              "Portage du launcher Python : sauvegardes et netplay arrivent "
                              "dans une prochaine version.")
                               .arg(QApplication::applicationVersion(), QT_VERSION_STR)
                               .arg(m_library.totalGames));
    });
}

void MainWindow::buildToolbar() {
    QToolBar *bar = addToolBar(tr("Barre d'outils"));
    bar->setMovable(false);
    bar->setToolButtonStyle(Qt::ToolButtonTextOnly);

    QAction *play = bar->addAction(tr("Démarrer"));
    connect(play, &QAction::triggered, this, &MainWindow::playSelected);
    QAction *refresh = bar->addAction(tr("Rafraîchir"));
    connect(refresh, &QAction::triggered, this, &MainWindow::refreshLibrary);
    QAction *settings = bar->addAction(tr("Paramètres"));
    connect(settings, &QAction::triggered, this, &MainWindow::openSettings);

    bar->addSeparator();
    bar->addWidget(new QLabel(tr(" Rechercher : "), this));
    m_search = new QLineEdit(this);
    m_search->setPlaceholderText(tr("titre ou fichier…"));
    m_search->setFixedWidth(220);
    connect(m_search, &QLineEdit::textChanged, this, &MainWindow::applyFilters);
    bar->addWidget(m_search);

    bar->addWidget(new QLabel(tr("  Console : "), this));
    m_consoleBox = new QComboBox(this);
    m_consoleBox->addItem(tr("Toutes les consoles"), QStringLiteral("all"));
    connect(m_consoleBox, &QComboBox::currentIndexChanged, this, &MainWindow::applyFilters);
    bar->addWidget(m_consoleBox);
}

void MainWindow::buildTable() {
    m_table = new QTableWidget(this);
    m_table->setColumnCount(6);
    m_table->setHorizontalHeaderLabels(
        {tr("Bannière"), tr("Titre"), tr("Console"), tr("Année"), tr("Taille"), tr("Fichier")});
    m_table->verticalHeader()->setVisible(false);
    m_table->verticalHeader()->setDefaultSectionSize(56);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_table->setAlternatingRowColors(true);
    m_table->setIconSize(QSize(64, 46));
    m_table->setSortingEnabled(true);
    m_table->setColumnWidth(0, 84);
    m_table->setColumnWidth(1, 280);
    m_table->setColumnWidth(2, 170);
    m_table->setColumnWidth(3, 70);
    m_table->setColumnWidth(4, 100);
    m_table->horizontalHeader()->setStretchLastSection(true);
    connect(m_table, &QTableWidget::cellDoubleClicked, this,
            [this](int row, int) { playRow(row); });
    setCentralWidget(m_table);
}

void MainWindow::refreshLibrary() {
    setStatus(tr("Chargement du catalogue…"));
    m_api->fetchLibrary(m_config.value("site_url").toString());
}

void MainWindow::onLibraryReady(const Library &library) {
    m_library = library;

    // Filtre par console (en conservant la sélection si possible).
    m_consoleBox->blockSignals(true);
    const QString current = m_consoleBox->currentData().toString();
    m_consoleBox->clear();
    m_consoleBox->addItem(tr("Toutes les consoles"), QStringLiteral("all"));
    for (const SystemInfo &system : m_library.systems) {
        m_consoleBox->addItem(system.label.isEmpty() ? system.id : system.label, system.id);
    }
    const int index = m_consoleBox->findData(current);
    m_consoleBox->setCurrentIndex(index >= 0 ? index : 0);
    m_consoleBox->blockSignals(false);

    m_table->setSortingEnabled(false);
    m_table->setRowCount(0);
    for (const SystemInfo &system : m_library.systems) {
        for (const Game &game : system.games) {
            const QString systemId = game.system.isEmpty() ? system.id : game.system;
            const int row = m_table->rowCount();
            m_table->insertRow(row);

            auto *banner = new QTableWidgetItem;
            banner->setData(SysRole, systemId);
            banner->setData(FileRole, game.file);
            banner->setData(NormRole, normalize(game.title + QLatin1Char(' ') + game.file));
            m_table->setItem(row, 0, banner);

            auto *title = new QTableWidgetItem(game.title.isEmpty() ? game.file : game.title);
            title->setToolTip(game.title.isEmpty() ? game.file : game.title);
            m_table->setItem(row, 1, title);

            auto *consoleItem = new QTableWidgetItem(system.label.isEmpty() ? system.id : system.label);
            m_table->setItem(row, 2, consoleItem);

            auto *year = new NumericItem(game.year > 0 ? QString::number(game.year) : QString());
            year->setData(Qt::UserRole, game.year);
            year->setTextAlignment(Qt::AlignCenter);
            m_table->setItem(row, 3, year);

            auto *size = new NumericItem(humanSize(game.size));
            size->setData(Qt::UserRole, game.size);
            size->setTextAlignment(Qt::AlignRight | Qt::AlignVCenter);
            m_table->setItem(row, 4, size);

            auto *fileItem = new QTableWidgetItem(game.file);
            fileItem->setToolTip(game.file);
            m_table->setItem(row, 5, fileItem);

            const QPixmap pixmap = m_covers->cover(systemId, game.file, game.cover);
            if (!pixmap.isNull()) {
                banner->setIcon(QIcon(scaleCover(pixmap)));
            }
        }
    }
    m_table->setSortingEnabled(true);
    m_table->sortItems(1, Qt::AscendingOrder);

    applyFilters();
    m_countLabel->setText(tr("%1 jeux").arg(m_library.totalGames));
    setStatus(tr("Bibliothèque chargée — %1 consoles.").arg(m_library.systems.size()));
}

void MainWindow::onLibraryFailed(const QString &error) {
    setStatus(tr("Catalogue indisponible."));
    QMessageBox::warning(this, tr("Catalogue indisponible"),
                         tr("Impossible de charger la bibliothèque depuis le site.\n\n%1\n\n"
                            "Vérifie la connexion, puis « Rafraîchir ».")
                             .arg(error));
}

void MainWindow::applyFilters() {
    const QString query = normalize(m_search->text().trimmed());
    const QString filter = m_consoleBox->currentData().toString();
    for (int row = 0; row < m_table->rowCount(); ++row) {
        const QTableWidgetItem *banner = m_table->item(row, 0);
        if (!banner) {
            continue;
        }
        const QString system = banner->data(SysRole).toString();
        const QString haystack = banner->data(NormRole).toString();
        const bool visible = (filter.isEmpty() || filter == QStringLiteral("all") || filter == system) &&
                             (query.isEmpty() || haystack.contains(query));
        m_table->setRowHidden(row, !visible);
    }
}

void MainWindow::playSelected() {
    const QList<QTableWidgetItem *> selection = m_table->selectedItems();
    if (selection.isEmpty()) {
        setStatus(tr("Sélectionne un jeu dans la liste."));
        return;
    }
    playRow(selection.first()->row());
}

void MainWindow::playRow(int row) {
    const QTableWidgetItem *banner = m_table->item(row, 0);
    if (!banner) {
        return;
    }
    const QString system = banner->data(SysRole).toString();
    const QString file = banner->data(FileRole).toString();
    const QString romsDir = m_config.value("roms_dir").toString().trimmed();
    if (romsDir.isEmpty()) {
        QMessageBox::warning(this, tr("Dossier ROMs manquant"),
                             tr("Ouvre Paramètres et indique le dossier des ROMs."));
        return;
    }

    QDir().mkpath(romsDir + QLatin1Char('/') + system);
    const QString romPath = romsDir + QLatin1Char('/') + system + QLatin1Char('/') + file;
    if (QFileInfo::exists(romPath)) {
        startLaunch(system, romPath);
        return;
    }
    if (!m_config.value("download_missing_roms").toBool(true)) {
        QMessageBox::warning(this, tr("ROM introuvable"),
                             tr("Fichier absent :\n%1").arg(romPath));
        return;
    }

    // Téléchargement depuis le site, avec progression.
    auto *out = new QFile(romPath);
    if (!out->open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        QMessageBox::critical(this, tr("Erreur"),
                              tr("Impossible d'écrire :\n%1").arg(romPath));
        delete out;
        return;
    }
    setStatus(tr("Téléchargement de %1…").arg(file));
    QNetworkReply *reply =
        m_api->downloadRom(m_config.value("site_url").toString(), system, file, out);

    auto *progress = new QProgressDialog(tr("Téléchargement de %1…").arg(file), tr("Annuler"),
                                         0, 100, this);
    progress->setWindowModality(Qt::WindowModal);
    progress->setMinimumDuration(0);
    connect(reply, &QNetworkReply::downloadProgress, progress,
            [progress](qint64 received, qint64 total) {
                if (total > 0) {
                    progress->setMaximum(100);
                    progress->setValue(static_cast<int>(received * 100 / total));
                }
            });
    connect(progress, &QProgressDialog::canceled, reply, &QNetworkReply::abort);
    connect(reply, &QNetworkReply::finished, this,
            [this, reply, out, progress, romPath, system, file]() {
                out->write(reply->readAll());
                out->close();
                out->deleteLater();
                reply->deleteLater();
                progress->deleteLater();
                if (reply->error() == QNetworkReply::OperationCanceledError) {
                    QFile::remove(romPath);
                    setStatus(tr("Téléchargement annulé."));
                    return;
                }
                if (reply->error() != QNetworkReply::NoError || QFileInfo(romPath).size() == 0) {
                    QFile::remove(romPath);
                    QMessageBox::critical(this, tr("Téléchargement impossible"),
                                          tr("Échec du téléchargement de %1.\n%2")
                                              .arg(file, reply->errorString()));
                    setStatus(tr("Échec du téléchargement."));
                    return;
                }
                startLaunch(system, romPath);
            });
    progress->show();
}

void MainWindow::startLaunch(const QString &system, const QString &romPath) {
    const LaunchOutcome outcome = launchGame(m_config, system, romPath);
    if (outcome.ok) {
        setStatus(outcome.message);
        return;
    }
    setStatus(tr("Échec du lancement."));
    QMessageBox::critical(this, tr("Lancement impossible"), outcome.message);
}

void MainWindow::setCover(const QString &system, const QString &file, const QPixmap &pixmap) {
    const QIcon icon(scaleCover(pixmap));
    for (int row = 0; row < m_table->rowCount(); ++row) {
        QTableWidgetItem *banner = m_table->item(row, 0);
        if (!banner) {
            continue;
        }
        if (banner->data(SysRole).toString() == system && banner->data(FileRole).toString() == file) {
            banner->setIcon(icon);
        }
    }
}

void MainWindow::openSettings() {
    SettingsDialog dialog(m_config, this);
    if (dialog.exec() != QDialog::Accepted) {
        return;
    }
    m_config = dialog.applyTo(m_config);
    saveConfig(m_config);
    m_covers->updateConfig(m_config.value("site_url").toString(),
                           m_config.value("roms_dir").toString());
    setStatus(tr("Paramètres enregistrés."));
    refreshLibrary();
}

void MainWindow::setStatus(const QString &text) {
    statusBar()->showMessage(text);
}

/// Ce que le launcher a trouvé (RetroArch, cores, émulateurs) — à copier en cas de souci.
void MainWindow::showDiagnostic() {
    QDialog dialog(this);
    dialog.setWindowTitle(tr("Diagnostic"));

    auto *text = new QPlainTextEdit(diagnosticReport(m_config), &dialog);
    text->setReadOnly(true);
    text->setMinimumSize(720, 460);

    auto *copy = new QPushButton(tr("Copier"), &dialog);
    connect(copy, &QPushButton::clicked, text,
            [text]() { QGuiApplication::clipboard()->setText(text->toPlainText()); });
    auto *close = new QPushButton(tr("Fermer"), &dialog);
    connect(close, &QPushButton::clicked, &dialog, &QDialog::accept);

    auto *buttons = new QHBoxLayout;
    buttons->addStretch(1);
    buttons->addWidget(copy);
    buttons->addWidget(close);

    auto *layout = new QVBoxLayout(&dialog);
    layout->addWidget(text);
    layout->addLayout(buttons);
    dialog.exec();
}
