"""Host-specific defaults; the shipped Windows settings and release stay unchanged."""
import os
import sys
from pathlib import Path


def data_directory():
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DescriberWorkbench'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/DescriberWorkbench'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'DescriberWorkbench'


def native_engine():return 'Windows' if sys.platform=='win32' else 'macOS' if sys.platform=='darwin' else 'eSpeak NG'


def narration_engines():
    return ['Windows','Windows 32-bit','Windows OneCore','OpenAI'] if sys.platform=='win32' else [native_engine(),'OpenAI']


def speech_label():return 'Windows speech' if sys.platform=='win32' else 'System speech'


def credential_label():return 'Windows DPAPI' if sys.platform=='win32' else 'macOS Keychain' if sys.platform=='darwin' else 'the desktop Secret Service keyring'


def native_text(text):
    if sys.platform=='win32':return text
    return text.replace('Windows DPAPI',credential_label()).replace('Windows speech','system speech').replace('Windows voice','native voice').replace('Windows export voice','native export voice').replace('Windows by default',native_engine()+' by default').replace('Windows engine','native engine').replace('Windows Settings','your operating system voice settings')


def external_environment():
    """Do not load frozen Python/Qt libraries into system media or voice tools."""
    env=dict(os.environ)
    if sys.platform=='linux' and getattr(sys,'frozen',False):
        original=env.pop('LD_LIBRARY_PATH_ORIG',None)
        if original is None:env.pop('LD_LIBRARY_PATH',None)
        else:env['LD_LIBRARY_PATH']=original
    return env


def keyring_secret(data,decrypt=False):
    """Store only an opaque reference in settings; never fall back to plaintext."""
    import uuid
    try:
        if sys.platform=='darwin':
            from keyring.backends.macOS import Keyring
        else:
            from keyring.backends.SecretService import Keyring
        backend=Keyring()
        if decrypt:
            reference=data.decode('ascii')
            if not reference.startswith('describer-keyring-v1:'):raise ValueError('Credential belongs to another platform.')
            value=backend.get_password('DescriberWorkbench',reference)
            if value is None:raise ValueError('Saved credential is missing or locked.')
            return value.encode('utf-8')
        reference='describer-keyring-v1:'+uuid.uuid4().hex
        backend.set_password('DescriberWorkbench',reference,data.decode('utf-8'))
        return reference.encode('ascii')
    except Exception as exc:
        raise RuntimeError('Cannot access '+credential_label()+'. Unlock the desktop keyring and retry; credentials were not saved as plaintext.') from exc
