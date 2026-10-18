#pragma once

#include <QDialog>
#include <QJsonObject>

class QCheckBox;
class QLineEdit;

class SettingsDialog : public QDialog {
    Q_OBJECT

public:
    explicit SettingsDialog(const QJsonObject &config, QWidget *parent = nullptr);

    // Renvoie la configuration mise à jour avec les valeurs du formulaire.
    QJsonObject applyTo(QJsonObject config) const;

private:
    QLineEdit *m_site;
    QLineEdit *m_roms;
    QLineEdit *m_retroarch;
    QLineEdit *m_cores;
    QCheckBox *m_download;
};
