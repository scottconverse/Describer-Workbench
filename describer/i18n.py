"""Workbench control translations, written for this reconstruction; English fallback."""
from PySide6.QtCore import Qt,QObject
from PySide6.QtWidgets import QPushButton,QLabel,QCheckBox,QGroupBox,QMenu,QDialog
from PySide6.QtGui import QAction
LANGUAGES=['English','Español','Français','Italiano','Português','Русский','Türkçe','Українська','Tiếng Việt','العربية']
KEYS=['Open video','Open URL','Analyze video','Settings','Cancel operation','Play / Pause','Speak descriptions','Start','End','Description','Add','Apply edit','Delete','Ask about scene','Explore scene','Export','Prompt preset','Manage presets','Character glossary','Help','&File','Open project','Save project','Import SRT / VTT','Manage voice presets','Check for updates','Import original data','Operation failed','Open a video to begin.']
ROWS=[
'Abrir vídeo|Abrir URL|Analizar vídeo|Ajustes|Cancelar operación|Reproducir / Pausar|Leer descripciones|Inicio|Fin|Descripción|Añadir|Aplicar cambios|Eliminar|Preguntar sobre la escena|Explorar escena|Exportar|Preajuste de instrucciones|Gestionar preajustes|Glosario de personajes|Ayuda|&Archivo|Abrir proyecto|Guardar proyecto|Importar SRT / VTT|Gestionar voces|Buscar actualizaciones|Importar datos originales|Error de operación|Abra un vídeo para empezar.',
'Ouvrir une vidéo|Ouvrir une URL|Analyser la vidéo|Paramètres|Annuler|Lecture / Pause|Lire les descriptions|Début|Fin|Description|Ajouter|Appliquer|Supprimer|Question sur la scène|Explorer la scène|Exporter|Consignes prédéfinies|Gérer les consignes|Glossaire des personnages|Aide|&Fichier|Ouvrir un projet|Enregistrer le projet|Importer SRT / VTT|Gérer les voix|Rechercher des mises à jour|Importer les données originales|Échec de l’opération|Ouvrez une vidéo pour commencer.',
'Apri video|Apri URL|Analizza video|Impostazioni|Annulla operazione|Riproduci / Pausa|Leggi descrizioni|Inizio|Fine|Descrizione|Aggiungi|Applica modifica|Elimina|Domanda sulla scena|Esplora scena|Esporta|Istruzioni predefinite|Gestisci istruzioni|Glossario personaggi|Aiuto|&File|Apri progetto|Salva progetto|Importa SRT / VTT|Gestisci voci|Cerca aggiornamenti|Importa dati originali|Operazione non riuscita|Apri un video per iniziare.',
'Abrir vídeo|Abrir URL|Analisar vídeo|Configurações|Cancelar operação|Reproduzir / Pausar|Ler descrições|Início|Fim|Descrição|Adicionar|Aplicar edição|Excluir|Perguntar sobre a cena|Explorar cena|Exportar|Instruções predefinidas|Gerenciar instruções|Glossário de personagens|Ajuda|&Arquivo|Abrir projeto|Salvar projeto|Importar SRT / VTT|Gerenciar vozes|Buscar atualizações|Importar dados originais|Falha na operação|Abra um vídeo para começar.',
'Открыть видео|Открыть URL|Анализ видео|Настройки|Отменить операцию|Пуск / Пауза|Озвучивать описания|Начало|Конец|Описание|Добавить|Применить|Удалить|Вопрос о сцене|Исследовать сцену|Экспорт|Шаблон запроса|Управление шаблонами|Словарь персонажей|Справка|&Файл|Открыть проект|Сохранить проект|Импорт SRT / VTT|Управление голосами|Проверить обновления|Импорт исходных данных|Ошибка операции|Откройте видео для начала.',
'Video aç|URL aç|Videoyu analiz et|Ayarlar|İşlemi iptal et|Oynat / Duraklat|Betimlemeleri seslendir|Başlangıç|Bitiş|Betimleme|Ekle|Değişikliği uygula|Sil|Sahne hakkında sor|Sahneyi keşfet|Dışa aktar|İstem şablonu|Şablonları yönet|Karakter sözlüğü|Yardım|&Dosya|Proje aç|Projeyi kaydet|SRT / VTT içe aktar|Sesleri yönet|Güncellemeleri denetle|Özgün verileri içe aktar|İşlem başarısız|Başlamak için video açın.',
'Відкрити відео|Відкрити URL|Аналіз відео|Налаштування|Скасувати операцію|Пуск / Пауза|Озвучувати описи|Початок|Кінець|Опис|Додати|Застосувати|Видалити|Запитання про сцену|Дослідити сцену|Експорт|Шаблон запиту|Керування шаблонами|Словник персонажів|Довідка|&Файл|Відкрити проєкт|Зберегти проєкт|Імпорт SRT / VTT|Керування голосами|Перевірити оновлення|Імпорт початкових даних|Помилка операції|Відкрийте відео для початку.',
'Mở video|Mở URL|Phân tích video|Cài đặt|Hủy thao tác|Phát / Tạm dừng|Đọc mô tả|Bắt đầu|Kết thúc|Mô tả|Thêm|Áp dụng sửa đổi|Xóa|Hỏi về cảnh|Khám phá cảnh|Xuất|Mẫu chỉ dẫn|Quản lý mẫu|Danh mục nhân vật|Trợ giúp|&Tệp|Mở dự án|Lưu dự án|Nhập SRT / VTT|Quản lý giọng nói|Kiểm tra cập nhật|Nhập dữ liệu gốc|Thao tác thất bại|Mở video để bắt đầu.',
'فتح فيديو|فتح رابط|تحليل الفيديو|الإعدادات|إلغاء العملية|تشغيل / إيقاف مؤقت|نطق الأوصاف|البداية|النهاية|الوصف|إضافة|تطبيق التعديل|حذف|سؤال عن المشهد|استكشاف المشهد|تصدير|قالب التعليمات|إدارة القوالب|قاموس الشخصيات|مساعدة|&ملف|فتح مشروع|حفظ المشروع|استيراد SRT / VTT|إدارة الأصوات|البحث عن تحديثات|استيراد البيانات الأصلية|فشلت العملية|افتح فيديو للبدء.'
]
TRANSLATIONS={language:dict(zip(KEYS,row.split('|'))) for language,row in zip(LANGUAGES[1:],ROWS)}

import json,sys
from pathlib import Path
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
CODES=dict(zip(LANGUAGES,['en','es','fr','it','pt','ru','tr','uk','vi','ar']))
try:ORIGINAL=json.loads((Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'assets/original-translations.json').read_text(encoding='utf8'))
except OSError:ORIGINAL={}

def translate(text,language):return TRANSLATIONS.get(language,{}).get(text,ORIGINAL.get(CODES.get(language),{}).get(text,text))

class DialogLanguage(QObject):
    def __init__(self,window):super().__init__(window);self.window=window
    def eventFilter(self,obj,event):
        parent=obj.parent()
        while parent is not None and parent is not self.window:parent=parent.parent()
        if isinstance(obj,QDialog) and parent is self.window and event.type()==QEvent.Type.Show:
            language=self.window.settings.data['ui_language'];apply_language(obj,language)
            source=obj.property('source_windowTitle') or obj.windowTitle();obj.setProperty('source_windowTitle',source);obj.setWindowTitle(translate(source,language))
        return False

def apply_language(window,language):
    window.setLayoutDirection(Qt.LayoutDirection.RightToLeft if language=='العربية' else Qt.LayoutDirection.LeftToRight)
    for obj in window.findChildren(QObject):
        if not isinstance(obj,(QPushButton,QLabel,QCheckBox,QGroupBox,QAction,QMenu,QDialog)):continue
        prop='title' if isinstance(obj,(QGroupBox,QMenu)) else 'windowTitle' if isinstance(obj,QDialog) else 'text'
        original=obj.property('source_'+prop)
        if original is None:
            original=obj.property(prop);obj.setProperty('source_'+prop,original)
        if isinstance(original,str) and original:
            current=obj.property(prop)
            known={translate(original,language) for language in LANGUAGES}|{original}
            if current not in known:original=current;obj.setProperty('source_'+prop,current)
            obj.setProperty(prop,translate(original,language))
    if hasattr(window,'table'):
        for i,label in enumerate(['Start','End','Description']):window.table.horizontalHeaderItem(i).setText(translate(label,language))
