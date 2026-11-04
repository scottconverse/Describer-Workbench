"""TownReporter-style provider/model selection adapted to a Qt desktop app."""
import copy
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QComboBox,QPushButton
from .models import discover,model_info
from .providers import PROVIDERS,model_id,set_model,destination


class ModelPicker(QWidget):
    reloaded=Signal()
    def __init__(self,window):
        super().__init__(window);self.window=window;self.rows=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);row=QHBoxLayout();layout.addLayout(row)
        row.addWidget(QLabel('Analysis AI'))
        self.provider=QComboBox();self.provider.setAccessibleName('Analysis AI provider');self.provider.addItems(PROVIDERS);row.addWidget(self.provider)
        self.model=QComboBox();self.model.setEditable(True);self.model.setAccessibleName('Analysis model');row.addWidget(self.model,1)
        self.refresh_button=QPushButton('Refresh models');row.addWidget(self.refresh_button);self.refresh_button.clicked.connect(self.refresh)
        self.test_button=QPushButton('Test connection');row.addWidget(self.test_button);self.test_button.clicked.connect(self.test)
        self.scope=QComboBox();self.scope.setAccessibleName('Analysis range');self.scope.addItems(['Whole video','Next 20 seconds','Next 60 seconds']);row.addWidget(self.scope)
        self.help=QLabel();self.help.setWordWrap(True);self.help.setAccessibleName('Analysis model status');layout.addWidget(self.help)
        self.provider.setCurrentText(window.settings.data['analysis_provider']);self.reload()
        self.provider.currentTextChanged.connect(self.provider_changed)
        self.model.currentIndexChanged.connect(self.model_selected)
        self.model.lineEdit().editingFinished.connect(self.model_edited)

    @property
    def data(self):
        return self.draft if getattr(self,'draft',None) is not None else self.window.settings.data

    def begin_draft(self):
        self.draft_token=object()
        self.draft=copy.deepcopy(self.window.settings.data)

    def end_draft(self,accepted):
        if accepted:self.window.settings.data.update(self.draft)
        self.draft=None;self.draft_token=None
        if not accepted and self.window.thread is not None:
            self.window.cancel.set();self.window.pending_model_test=None
        self.provider.blockSignals(True);self.provider.setCurrentText(self.data['analysis_provider']);self.provider.blockSignals(False)
        self.reload()

    def reload(self):
        settings=self.data;provider=self.provider.currentText()
        self.model.blockSignals(True);self.model.clear()
        if provider!='Gemini':
            for row in self.rows:
                label=row['name']+(' · cloud · uses allowance' if row['cloud'] else ' · local')+(' · vision unknown' if row['vision'] is None else ' · vision' if row['vision'] else ' · no vision')+(' · loaded' if row['loaded'] else '')
                self.model.addItem(label,row['name'])
        else:self.model.addItem(settings['model'],settings['model'])
        selected=model_id(settings);index=self.model.findData(selected)
        if index>=0:self.model.setCurrentIndex(index)
        else:self.model.setCurrentIndex(-1);self.model.setEditText(selected)
        self.model.blockSignals(False);self.refresh_button.setEnabled(provider not in ('Gemini','Anthropic API'));self.test_button.setEnabled(provider!='Gemini');self.status();self.reloaded.emit()

    def status(self):
        if self.provider.currentText()=='Gemini':
            self.help.setText('Gemini uploads video with audio unless removed in Settings. Uses your Google API key.');return
        if self.provider.currentText()!='Ollama':
            try:note=destination(self.data)
            except ValueError as exc:note=str(exc)
            self.help.setText(note+'. Capability is unverified until an image-backed request succeeds. Exact selected model: '+(model_id(self.data) or 'not selected')+'.');return
        name=self.data['ollama_model'];row=next((r for r in self.rows if r['name']==name),None)
        place=('Cloud model: frames leave this computer and use your Ollama allowance. ' if row and row['cloud'] else 'Local Ollama model. ' if row else 'Refresh to check this exact model. ')
        self.help.setText(place+('Capability discovery is unavailable; retry before analysis. ' if row and row['vision'] is None else 'This model does not report vision support. ' if row and not row['vision'] else '')+'Analysis sends sampled frames without audio; review description timing and dialogue gaps.')

    def save(self):
        if getattr(self,'draft',None) is not None:return
        try:self.window.settings.save()
        except Exception as exc:self.window.error(str(exc))

    def provider_changed(self,value):
        self.data['analysis_provider']=value;self.rows=[];self.reload();self.save()

    def model_selected(self,index):
        name=self.model.itemData(index)
        if name:self.store_model(name)

    def model_edited(self):
        index=self.model.currentIndex()
        name=self.model.itemData(index) if index>=0 and self.model.currentText()==self.model.itemText(index) else self.model.currentText().strip()
        if name:self.store_model(name)

    def store_model(self,name):
        set_model(self.data,name)
        self.model.blockSignals(True)
        index=self.model.findData(name)
        if index>=0:self.model.setCurrentIndex(index)
        else:self.model.setCurrentIndex(-1);self.model.setEditText(name)
        self.model.blockSignals(False);self.status();self.save()

    def refresh(self):
        if self.window.busy() or self.provider.currentText()=='Gemini':return
        settings=copy.deepcopy(self.data)
        token=getattr(self,'draft_token',None)
        if self.provider.currentText()=='Ollama':fetch=discover
        else:
            from .subscriptions import discover as fetch
        self.window.job(lambda c,l:fetch(settings,c,l),lambda rows:self.discovered(rows) if token is getattr(self,'draft_token',None) and self.data==settings else None)

    def discovered(self,rows):
        self.rows=rows;self.reload()

    def test(self):
        if self.window.busy() or self.provider.currentText()=='Gemini':return
        self.model_edited()
        settings=copy.deepcopy(self.data)
        token=getattr(self,'draft_token',None)
        def ready(info):
            if self.window.cancel.is_set() or token is not getattr(self,'draft_token',None) or self.data!=settings:return
            if settings['analysis_provider']=='Ollama':
                if not self.window.confirm_ollama(info,settings):return
            elif not self.window.cloud_confirm(settings):return
            # Discovery callback still owns its QThread until teardown.
            self.window.pending_model_test=settings
        if settings['analysis_provider']=='Ollama':check=model_info
        else:
            from .subscriptions import model_info as check
        self.window.job(lambda c,l:check(settings),ready)
