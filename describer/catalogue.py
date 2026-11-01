"""Built-in genre prompts matching the original catalogue's purposes."""
PROMPTS={
 'Movie Trailer':'Prioritize impactful shots, character introductions, title cards and release dates. Keep each description brief enough for rapid cuts; avoid spoilers.',
 'Action Movie':'Describe decisive movement, choreography, weapons, chases and changes in the action. Keep timing clear and concise.',
 'Romantic Movie':'Describe significant looks, gestures, touch, distance between characters and visual atmosphere.',
 'Comedy / Sitcom':'Describe the visual gag and reactions at the moment needed to understand the joke, without explaining audible dialogue.',
 'Sci-Fi / Fantasy':'Describe unfamiliar environments, creatures, technology and visible magical effects with concrete language.',
 'Meme / Viral Video':'Describe the central visual action, unexpected change and any text needed to understand the short clip.',
 'Documentary / Educational':'Prioritize relevant demonstrations, diagrams, maps, labels, archival images and on-screen text.',
 'Cooking / Recipe':'Describe ingredients, tools, techniques and visible changes in food texture, color and consistency.',
 'DIY / Tutorial':'Describe the tools, materials and each visible step, including the state before and after the action.',
 "Gaming / Let's Play":'Describe important avatar actions and meaningful changes to game interfaces, health, objectives and maps.'}

VOICE_PRESETS={
 'Narrator':{'base_voice':'alloy','speed':1.0,'instructions':'Speak clearly with a steady narration tone.'},
 'Narrator - Fast':{'base_voice':'alloy','speed':1.2,'instructions':'Use a clear, brisk narration pace.'},
 'Character - Energetic':{'base_voice':'nova','speed':1.1,'instructions':'Use an upbeat, lively delivery.'},
 'Character - Deliberate':{'base_voice':'onyx','speed':.85,'instructions':'Use a measured, serious delivery.'},
 'Whisper':{'base_voice':'shimmer','speed':.9,'instructions':'Speak softly in a whisper.'}}
