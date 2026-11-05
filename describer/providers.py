"""Shared analysis-provider identity checks, independent of UI and transport."""

PROVIDERS = ('Gemini', 'Ollama', 'Subscription gateway', 'Codex CLI', 'Claude CLI',
             'Gemini CLI', 'OpenAI-compatible', 'Anthropic API')


def provider_name(settings):
    name = settings.get('analysis_provider', 'Gemini')
    if name not in PROVIDERS:
        raise ValueError('Unsupported analysis provider. Choose a configured provider in Settings; no request was sent.')
    return name


def model_id(settings):
    provider=provider_name(settings)
    if provider=='Gemini':return settings.get('model','')
    if provider=='Ollama':return settings.get('ollama_model','')
    if provider=='OpenAI-compatible':return settings.get('connections',{}).get(settings.get('connection_id',''),{}).get('model','').strip()
    return settings.get('provider_models',{}).get(provider,'').strip()


def set_model(settings, name):
    provider=provider_name(settings)
    if provider=='Gemini':settings['model']=name
    elif provider=='Ollama':settings['ollama_model']=name
    elif provider=='OpenAI-compatible':
        entry=settings.get('connections',{}).get(settings.get('connection_id',''))
        if entry is None:raise ValueError('Configure and select a compatible connection before choosing its model.')
        entry['model']=name
    else:settings.setdefault('provider_models',{})[provider]=name


def remote(settings):
    provider=provider_name(settings)
    if provider=='Ollama':
        from .models import is_cloud,model_info
        return is_cloud(settings,model_info(settings))
    if provider=='OpenAI-compatible':
        from .subscriptions import connection
        from .models import is_loopback
        return not is_loopback(connection(settings)['url'])
    return True


def destination(settings):
    provider=provider_name(settings)
    if provider=='Gemini':return 'Google Gemini API (video, with audio unless removed)'
    if provider=='Ollama':return 'Ollama at '+settings.get('ollama_url','')+' (sampled images, no audio)'
    if provider in ('Subscription gateway','OpenAI-compatible'):
        from .subscriptions import connection
        forwarding='; gateway forwards to the selected subscription provider' if provider=='Subscription gateway' else ''
        return provider+' at '+connection(settings)['url']+' (sampled images and prompts, no audio'+forwarding+')'
    return provider+' (sampled images and prompts, no audio; uses the selected provider account)'
