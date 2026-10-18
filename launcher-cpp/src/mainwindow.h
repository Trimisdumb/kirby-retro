#pragma once

#include <QJsonObject>
#include <QMainWindow>
#include <QPixmap>

#include "api.h"

class QComboBox;
class QLabel;
class QLineEdit;
class QTableWidget;

class CoverLoader;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    MainWindow();

private slots:
    void refreshLibrary();
    void onLibraryReady(const Library &library);
    void onLibraryFailed(const QString &error);
    void applyFilters();
    void playSelected();
    void openSettings();

private:
    void buildMenus();
    void buildToolbar();
    void buildTable();
    void setStatus(const QString &text);
    void playRow(int row);
    void startLaunch(const QString &system, const QString &romPath);
    void setCover(const QString &system, const QString &file, const QPixmap &pixmap);

    QJsonObject m_config;
    Library m_library;
    Api *m_api;
    CoverLoader *m_covers;
    QTableWidget *m_table;
    QLineEdit *m_search;
    QComboBox *m_consoleBox;
    QLabel *m_countLabel;
};
