"""Structured stage completion and reported usage, without Qt or time estimates."""

STAGES = {
    'describe': ('protected-audio', 'observation', 'narration'),
    'prepare': ('protected-audio', 'narration'),
    'export': ('protected-audio', 'narration', 'export'),
    'ask': ('scene',), 'explore': ('scene',), 'voice-preview': ('voice-preview',),
}
LABELS = {'protected-audio':'Protect original audio', 'observation':'Observe video',
          'narration':'Measure and place narration', 'export':'Write export',
          'scene':'Analyze scene', 'voice-preview':'Synthesize preview'}


def pipeline(operation, text_export=False):
    names = ('export',) if text_export else STAGES[operation]
    return {'percent':0, 'stages':[{'id':name,'label':LABELS[name],'state':'pending','completed':0,'total':None} for name in names]}


def advance(value, name, completed=0, total=None):
    import copy
    value=copy.deepcopy(value)
    names=[row['id'] for row in value['stages']]
    if name not in names:return value
    index=names.index(name)
    for i,row in enumerate(value['stages']):
        if i<index:row.update(state='done',completed=1,total=1)
        elif i==index:
            if row['state']=='done':continue
            row.update(state='done' if total is not None and completed>=total else 'current',completed=completed,total=total)
    fractions=[1 if row['state']=='done' else min(1,row['completed']/row['total']) if row['total'] else 0 for row in value['stages']]
    value['percent']=round(100*sum(fractions)/len(fractions))
    return value


def stage(log, name, completed=0, total=None):
    callback=getattr(log,'stage',None)
    if callback:callback(name,completed,total)


def usage(log, provider, requested_model, reported_model=None, input_tokens=None, output_tokens=None, total_tokens=None):
    def count(value):
        return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None
    callback=getattr(log,'usage',None)
    if callback:
        callback({'provider':provider,'requested_model':requested_model,'reported_model':reported_model,
                  'input_tokens':count(input_tokens),'output_tokens':count(output_tokens),'total_tokens':count(total_tokens)})
