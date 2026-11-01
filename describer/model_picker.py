"""TownReporter-style provider/model selection adapted to a Qt desktop app."""
import copy
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QComboBox,QPushButton
from .models import discover,model_info,is_cloud,test_connection


class ModelPicker(QWidget):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.rows=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);row=QHBoxLayout();layout.addLayout(row)
        row.addWidget(QLabel('Analysis AI'))
        self.provider=QComboBox();self.provider.setAccessibleName('Analysis AI provider');self.provider.addItems(['Gemini','Ollama']);row.addWidget(self.provider)
        self.model=QComboBox();self.model.setEditable(True);self.model.setAccessibleName('Analysis model');row.addWidget(self.model,1)
        self.refresh_button=QPushButton('Refresh models');row.addWidget(self.refresh_button);self.refresh_button.clicked.connect(self.refresh)
        self.test_button=QPushButton('Test connection');row.addWidget(self.test_button);self.test_button.clicked.connect(self.test)
        self.scope=QComboBox();self.scope.setAccessibleName('Analysis range');self.scope.addItems(['Whole video','Next 20 seconds','Next 60 seconds']);row.addWidget(self.scope)
        self.help=QLabel();self.help.setWordWrap(True);self.help.setAccessibleName('Analysis model status');layout.addWidget(self.help)
        self.provider.setCurrentText(window.settings.data['analysis_provider']);self.reload()
        self.provider.currentTextChanged.connect(self.provider_changed)
        self.model.currentIndexChanged.connect(self.model_selected)
        self.model.lineEdit().editingFinished.connect(self.model_edited)

    def reload(self):
        settings=self.window.settings.data;ollama=self.provider.currentText()=='Ollama'
        self.model.blockSignals(True);self.model.clear()
        if ollama:
            for row in self.rows:
                label=row['name']+(' · cloud · uses allowance' if row['cloud'] else ' · local')+(' · vision' if row['vision'] else ' · no vision')+(' · loaded' if row['loaded'] else '')
                self.model.addItem(label,row['name'])
        else:self.model.addItem(settings['model'],settings['model'])
        selected=settings['ollama_model' if ollama else 'model'];index=self.model.findData(selected)
        if index>=0:self.model.setCurrentIndex(index)
        else:self.model.setCurrentIndex(-1);self.model.setEditText(selected)
        self.model.blockSignals(False);self.refresh_button.setEnabled(ollama);self.test_button.setEnabled(ollama);self.status()

    def status(self):
        if self.provider.currentText()=='Gemini':
            self.help.setText('Gemini uploads video with audio unless removed in Settings. Uses your Google API key.');return
        name=self.window.settings.data['ollama_model'];row=next((r for r in self.rows if r['name']==name),None)
        place=('Cloud model: frames leave this computer and use your Ollama allowance. ' if row and row['cloud'] else 'Local Ollama model. ' if row else 'Refresh to check this exact model. ')
        self.help.setText(place+('This model does not report vision support. ' if row and not row['vision'] else '')+'Analysis sends sampled frames without audio; review description timing and dialogue gaps.')

    def save(self):
        try:self.window.settings.save()
        except Exception as exc:self.window.error(str(exc))

    def provider_changed(self,value):
        self.window.settings.data['analysis_provider']=value;self.reload();self.save()

    def model_selected(self,index):
        name=self.model.itemData(index)
        if name:self.store_model(name)

    def model_edited(self):
        index=self.model.currentIndex()
        name=self.model.itemData(index) if index>=0 and self.model.currentText()==self.model.itemText(index) else self.model.currentText().strip()
        if name:self.store_model(name)

    def store_model(self,name):
        key='ollama_model' if self.provider.currentText()=='Ollama' else 'model'
        self.window.settings.data[key]=name;self.status();self.save()

    def refresh(self):
        if self.window.busy():return
        settings=copy.deepcopy(self.window.settings.data)
        self.window.job(lambda c,l:discover(settings,c,l),self.discovered)

    def discovered(self,rows):
        self.rows=rows;self.reload()

    def test(self):
        if self.window.busy():return
        self.model_edited()
        settings=copy.deepcopy(self.window.settings.data)
        def ready(info):
            if self.window.cancel.is_set():return
            if not self.window.confirm_ollama(info):return
            # Discovery callback still owns its QThread until teardown.
            self.window.pending_model_test=settings
        self.window.job(lambda c,l:model_info(settings),ready)
