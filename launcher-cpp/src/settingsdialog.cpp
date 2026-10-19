#include "settingsdialog.h"

#include <QCheckBox>
#include <QDialogButtonBox>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QVBoxLayout>

#include "detect.h"

namespace {

// Ligne « champ + bouton Parcourir » pour choisir un dossier.
QWidget *browseRow(QLineEdit *edit, const QString &title, QWidget *parent) {
    auto *row = new QWidget(parent);
    auto *layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(edit, 1);
    auto *button = new QPushButton(QObject::tr("Parcourir…"), row);
    layout->addWidget(button);
    QObject::connect(button, &QPushButton::clicked, edit, [edit, title, parent]() {
        const QString dir = QFileDialog::getExistingDirectory(parent, title, edit->text());
        if (!dir.isEmpty()) {
            edit->setText(dir);
        }
    });
    return row;
}

// Même chose, mais pour choisir un fichier (retroarch.exe).
QWidget *fileRow(QLineEdit *edit, const QString &title, const QString &filter, QWidget *parent) {
    auto *row = new QWidget(parent);
    auto *layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(edit, 1);
    auto *button = new QPushButton(QObject::tr("Parcourir…"), row);
    layout->addWidget(button);
    QObject::connect(button, &QPushButton::clicked, edit, [edit, title, filter, parent]() {
        const QFileInfo current(edit->text().trimmed());
        const QString start =
            current.isDir() ? current.absoluteFilePath() : current.absolutePath();
        const QString file = QFileDialog::getOpenFileName(parent, title, start, filter);
        if (!file.isEmpty()) {
            edit->setText(file);
        }
    });
    return row;
}

}  // namespace

SettingsDialog::SettingsDialog(const QJsonObject &config, QWidget *parent) : QDialog(parent) {
    setWindowTitle(tr("Paramètres"));
    setMinimumWidth(640);

    const QJsonObject retroarch = config.value("retroarch").toObject();
    m_site = new QLineEdit(config.value("site_url").toString(), this);
    m_roms = new QLineEdit(config.value("roms_dir").toString(), this);
    m_retroarch = new QLineEdit(retroarch.value("path").toString(), this);
    m_cores = new QLineEdit(retroarch.value("cores_dir").toString(), this);
    m_download = new QCheckBox(tr("Télécharger les ROMs manquantes depuis le site"), this);
    m_download->setChecked(config.value("download_missing_roms").toBool(true));

    auto *form = new QFormLayout;
    form->addRow(tr("Site"), m_site);
    form->addRow(tr("Dossier ROMs"), browseRow(m_roms, tr("Choisis le dossier des ROMs"), this));
    form->addRow(tr("RetroArch (retroarch.exe)"),
                 fileRow(m_retroarch, tr("Choisis retroarch.exe dans le dossier de RetroArch"),
                         tr("RetroArch (retroarch.exe retroarch);;Tous les fichiers (*)"), this));
    form->addRow(tr("Dossier cores"), browseRow(m_cores, tr("Choisis le dossier des cores libretro"), this));

    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);

    auto *hint = new QLabel(tr("Sauvegardes, netplay et protocole kirbyretro:// : repris dans une "
                               "prochaine version du portage.\n"
                               "Un souci de lancement ? « Aide → Diagnostic… » liste RetroArch, "
                               "les cores et les émulateurs trouvés."));
    hint->setWordWrap(true);
    hint->setEnabled(false);

    auto *layout = new QVBoxLayout(this);
    layout->addLayout(form);
    layout->addWidget(m_download);
    layout->addWidget(hint);
    layout->addWidget(buttons);
}

QJsonObject SettingsDialog::applyTo(QJsonObject config) const {
    const QString site = m_site->text().trimmed();
    config["site_url"] = site.isEmpty() ? QStringLiteral("https://retro.kirbytrim.buzz") : site;
    config["roms_dir"] = m_roms->text().trimmed();
    config["download_missing_roms"] = m_download->isChecked();

    QJsonObject retroarch = config.value("retroarch").toObject();
    // Un dossier reste accepté, mais on enregistre le chemin de l'exécutable.
    const QString typed = m_retroarch->text().trimmed();
    const QString exe = retroarchExecutable(typed);
    retroarch["path"] = exe.isEmpty() ? typed : exe;
    retroarch["cores_dir"] = m_cores->text().trimmed();
    config["retroarch"] = retroarch;
    return config;
}
