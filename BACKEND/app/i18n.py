"""
Lightweight multilingual layer for Indian languages.

Rather than depend on a paid translation API (fragile in a hackathon demo),
core response templates are pre-translated for the languages below and
filled in with live data at runtime. Free-form LLM answers (see llm.py) are
asked to respond directly in the requested language when an LLM key is
configured. Add a new language by adding one dict entry — no other code
changes needed.
"""
from __future__ import annotations

SUPPORTED = {
    "en": {"name": "English", "speech": "en-IN"},
    "hinglish": {"name": "Hinglish (Hindi + English)", "speech": "hi-IN"},
    "hi": {"name": "हिन्दी", "speech": "hi-IN"},
    "bn": {"name": "বাংলা", "speech": "bn-IN"},
    "ta": {"name": "தமிழ்", "speech": "ta-IN"},
    "te": {"name": "తెలుగు", "speech": "te-IN"},
    "mr": {"name": "मराठी", "speech": "mr-IN"},
    "gu": {"name": "ગુજરાતી", "speech": "gu-IN"},
    "pa": {"name": "ਪੰਜਾਬੀ", "speech": "pa-IN"},
    "kn": {"name": "ಕನ್ನಡ", "speech": "kn-IN"},
    "ml": {"name": "മലയാളം", "speech": "ml-IN"},
    "or": {"name": "ଓଡ଼ିଆ", "speech": "or-IN"},
    "ur": {"name": "اردو", "speech": "ur-IN"},
}

ALERT_LABEL = {
    "green": {"en": "Green (No warning)", "hi": "हरा (कोई चेतावनी नहीं)", "bn": "সবুজ (কোনো সতর্কতা নেই)",
              "ta": "பச்சை (எச்சரிக்கை இல்லை)", "te": "గ్రీన్ (హెచ్చరిక లేదు)", "mr": "हिरवा (इशारा नाही)",
              "gu": "લીલો (કોઈ ચેતવણી નથી)", "pa": "ਹਰਾ (ਕੋਈ ਚੇਤਾਵਨੀ ਨਹੀਂ)", "kn": "ಹಸಿರು (ಎಚ್ಚರಿಕೆ ಇಲ್ಲ)",
              "ml": "പച്ച (മുന്നറിയിപ്പ് ഇല്ല)", "or": "ସବୁଜ (କୌଣସି ଚେତାବନୀ ନାହିଁ)", "ur": "سبز (کوئی وارننگ نہیں)"},
    "yellow": {"en": "Yellow (Watch)", "hi": "पीला (सतर्क रहें)", "bn": "হলুদ (সতর্কতা)", "ta": "மஞ்சள் (கவனிக்கவும்)",
               "te": "పసుపు (గమనించండి)", "mr": "पिवळा (सावध रहा)", "gu": "પીળો (સાવચેત રહો)",
               "pa": "ਪੀਲਾ (ਸੁਚੇਤ ਰਹੋ)", "kn": "ಹಳದಿ (ಎಚ್ಚರಿಕೆಯಿಂದಿರಿ)", "ml": "മഞ്ഞ (ജാഗ്രത)",
               "or": "ହଳଦିଆ (ସତର୍କ ରୁହନ୍ତୁ)", "ur": "پیلا (چوکنا رہیں)"},
    "orange": {"en": "Orange (Be prepared)", "hi": "नारंगी (तैयार रहें)", "bn": "কমলা (প্রস্তুত থাকুন)",
               "ta": "ஆரஞ்சு (தயாராக இருங்கள்)", "te": "నారింజ (సిద్ధంగా ఉండండి)", "mr": "नारिंगी (सज्ज रहा)",
               "gu": "નારંગી (તૈયાર રહો)", "pa": "ਸੰਤਰੀ (ਤਿਆਰ ਰਹੋ)", "kn": "ಕಿತ್ತಳೆ (ಸಿದ್ಧರಾಗಿರಿ)",
               "ml": "ഓറഞ്ച് (തയ്യാറാകുക)", "or": "କମଳା (ପ୍ରସ୍ତୁତ ରୁହନ୍ତୁ)", "ur": "نارنجی (تیار رہیں)"},
    "red": {"en": "Red (Take action)", "hi": "लाल (कार्रवाई करें)", "bn": "লাল (ব্যবস্থা নিন)", "ta": "சிவப்பு (நடவடிக்கை எடுக்கவும்)",
            "te": "ఎరుపు (చర్య తీసుకోండి)", "mr": "लाल (कृती करा)", "gu": "લાલ (પગલાં લો)",
            "pa": "ਲਾਲ (ਕਾਰਵਾਈ ਕਰੋ)", "kn": "ಕೆಂಪು (ಕ್ರಮ ಕೈಗೊಳ್ಳಿ)", "ml": "ചുവപ്പ് (നടപടി സ്വീകരിക്കുക)",
            "or": "ଲାଲ (ପଦକ୍ଷେପ ନିଅନ୍ତୁ)", "ur": "سرخ (کارروائی کریں)"},
}

# {location}, {temp}, {tmin}, {tmax}, {condition}, {rain_prob}, {wind} are filled at runtime
CURRENT_TEMPLATE = {
    "en": "Weather in {location}: {condition}, {temp}°C right now (range {tmin}–{tmax}°C). "
          "Rain chance {rain_prob}%, wind {wind} km/h.",
    "hi": "{location} में मौसम: {condition}, अभी {temp}°C (सीमा {tmin}–{tmax}°C)। "
          "बारिश की संभावना {rain_prob}%, हवा {wind} किमी/घंटा।",
    "bn": "{location}-এ আবহাওয়া: {condition}, এখন {temp}°সে (সীমা {tmin}–{tmax}°সে)। "
          "বৃষ্টির সম্ভাবনা {rain_prob}%, বাতাস {wind} কিমি/ঘণ্টা।",
    "ta": "{location} வானிலை: {condition}, இப்போது {temp}°C (வரம்பு {tmin}–{tmax}°C). "
          "மழை வாய்ப்பு {rain_prob}%, காற்று {wind} கிமீ/மணி.",
    "te": "{location} వాతావరణం: {condition}, ప్రస్తుతం {temp}°C (పరిధి {tmin}–{tmax}°C). "
          "వర్షం అవకాశం {rain_prob}%, గాలి {wind} కి.మీ/గం.",
    "mr": "{location} मधील हवामान: {condition}, सध्या {temp}°C (श्रेणी {tmin}–{tmax}°C). "
          "पावसाची शक्यता {rain_prob}%, वारा {wind} किमी/तास.",
    "gu": "{location} માં હવામાન: {condition}, હાલમાં {temp}°C (શ્રેણી {tmin}–{tmax}°C). "
          "વરસાદની શક્યતા {rain_prob}%, પવન {wind} કિમી/કલાક.",
    "pa": "{location} ਵਿੱਚ ਮੌਸਮ: {condition}, ਹੁਣ {temp}°C (ਰੇਂਜ {tmin}–{tmax}°C)। "
          "ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ {rain_prob}%, ਹਵਾ {wind} ਕਿਮੀ/ਘੰਟਾ।",
    "kn": "{location} ನಲ್ಲಿ ಹವಾಮಾನ: {condition}, ಈಗ {temp}°C (ವ್ಯಾಪ್ತಿ {tmin}–{tmax}°C). "
          "ಮಳೆಯ ಸಾಧ್ಯತೆ {rain_prob}%, ಗಾಳಿ {wind} ಕಿಮೀ/ಗಂ.",
    "ml": "{location} ലെ കാലാവസ്ഥ: {condition}, ഇപ്പോൾ {temp}°C (പരിധി {tmin}–{tmax}°C). "
          "മഴ സാധ്യത {rain_prob}%, കാറ്റ് {wind} കി.മീ/മണിക്കൂർ.",
    "or": "{location} ର ପାଣିପାଗ: {condition}, ବର୍ତ୍ତମାନ {temp}°C (ପରିସର {tmin}–{tmax}°C)। "
          "ବର୍ଷାର ସମ୍ଭାବନା {rain_prob}%, ପବନ {wind} କିମି/ଘଣ୍ଟା।",
    "ur": "{location} کا موسم: {condition}، ابھی {temp}°C (رینج {tmin}–{tmax}°C)۔ "
          "بارش کا امکان {rain_prob}%، ہوا {wind} کلومیٹر/گھنٹہ۔",
}

NO_LOCATION_PROMPT = {
    "en": "Which place would you like the weather for? You can also tap the location button.",
    "hi": "आप किस स्थान का मौसम जानना चाहते हैं? आप लोकेशन बटन भी दबा सकते हैं।",
    "bn": "আপনি কোন স্থানের আবহাওয়া জানতে চান? আপনি লোকেশন বোতামও চাপতে পারেন।",
    "ta": "எந்த இடத்திற்கான வானிலையை அறிய விரும்புகிறீர்கள்? இருப்பிடப் பொத்தானையும் தட்டலாம்.",
    "te": "మీరు ఏ ప్రదేశం వాతావరణం తెలుసుకోవాలనుకుంటున్నారు? లొకేషన్ బటన్ కూడా నొక్కవచ్చు.",
    "mr": "तुम्हाला कोणत्या ठिकाणचे हवामान हवे आहे? तुम्ही लोकेशन बटण देखील दाबू शकता.",
    "gu": "તમે કયા સ્થળનું હવામાન જાણવા માંગો છો? તમે લોકેશન બટન પણ દબાવી શકો છો.",
    "pa": "ਤੁਸੀਂ ਕਿਸ ਸਥਾਨ ਦਾ ਮੌਸਮ ਜਾਣਨਾ ਚਾਹੁੰਦੇ ਹੋ? ਤੁਸੀਂ ਲੋਕੇਸ਼ਨ ਬਟਨ ਵੀ ਦਬਾ ਸਕਦੇ ਹੋ।",
    "kn": "ನೀವು ಯಾವ ಸ್ಥಳದ ಹವಾಮಾನ ತಿಳಿಯಬೇಕು? ಲೊಕೇಶನ್ ಬಟನ್ ಅನ್ನೂ ಒತ್ತಬಹುದು.",
    "ml": "ഏത് സ്ഥലത്തെ കാലാവസ്ഥയാണ് അറിയേണ്ടത്? ലൊക്കേഷൻ ബട്ടണും അമർത്താം.",
    "or": "ଆପଣ କେଉଁ ସ୍ଥାନର ପାଣିପାଗ ଜାଣିବାକୁ ଚାହାଁନ୍ତି? ଆପଣ ଲୋକେସନ ବଟନ ମଧ୍ୟ ଦବାଇ ପାରିବେ।",
    "ur": "آپ کس جگہ کا موسم جاننا چاہتے ہیں؟ آپ لوکیشن بٹن بھی دبا سکتے ہیں۔",
}

LOCATION_NOT_FOUND = {
    "en": "I couldn't find that place. Could you check the spelling or try a nearby bigger town?",
    "hi": "मुझे वह स्थान नहीं मिला। कृपया वर्तनी जांचें या पास के बड़े शहर का नाम आज़माएँ।",
    "bn": "আমি সেই স্থানটি খুঁজে পাইনি। বানান পরীক্ষা করুন বা কাছের বড় শহরের নাম ব্যবহার করুন।",
    "ta": "அந்த இடத்தை என்னால் கண்டுபிடிக்க முடியவில்லை. எழுத்துப்பிழையை சரிபார்க்கவும்.",
    "te": "ఆ ప్రదేశం కనుగొనబడలేదు. స్పెల్లింగ్ చెక్ చేయండి లేదా దగ్గరి పెద్ద పట్టణం ప్రయత్నించండి.",
    "mr": "ते ठिकाण सापडले नाही. स्पेलिंग तपासा किंवा जवळच्या मोठ्या शहराचे नाव वापरा.",
    "gu": "તે સ્થળ મળ્યું નથી. જોડણી તપાસો અથવા નજીકના મોટા શહેરનું નામ અજમાવો.",
    "pa": "ਉਹ ਸਥਾਨ ਨਹੀਂ ਮਿਲਿਆ। ਸਪੈਲਿੰਗ ਦੀ ਜਾਂਚ ਕਰੋ ਜਾਂ ਨੇੜਲੇ ਵੱਡੇ ਸ਼ਹਿਰ ਦਾ ਨਾਂ ਵਰਤੋ।",
    "kn": "ಆ ಸ್ಥಳ ಸಿಗಲಿಲ್ಲ. ಕಾಗುಣಿತ ಪರಿಶೀಲಿಸಿ ಅಥವಾ ಹತ್ತಿರದ ದೊಡ್ಡ ಪಟ್ಟಣ ಪ್ರಯತ್ನಿಸಿ.",
    "ml": "ആ സ്ഥലം കണ്ടെത്താനായില്ല. സ്പെല്ലിംഗ് പരിശോധിക്കുക അല്ലെങ്കിൽ അടുത്തുള്ള വലിയ പട്ടണം ശ്രമിക്കുക.",
    "or": "ମୁଁ ସେହି ସ୍ଥାନ ପାଇଲି ନାହିଁ। ବନାନ ଯାଞ୍ଚ କରନ୍ତୁ କିମ୍ବା ନିକଟସ୍ଥ ବଡ଼ ସହରର ନାମ ଚେଷ୍ଟା କରନ୍ତୁ।",
    "ur": "مجھے وہ جگہ نہیں ملی۔ ہجے چیک کریں یا قریبی بڑے شہر کا نام آزمائیں۔",
}


def t(table: dict[str, str], lang: str) -> str:
    return table.get(lang, table.get("en", ""))


def alert_label(level: str, lang: str) -> str:
    level_dict = ALERT_LABEL.get(level, ALERT_LABEL["green"])
    return level_dict.get(lang, level_dict.get("en", "Green"))



# Hinglish uses Roman-script Hindi + English for a natural hackathon-demo experience.
CURRENT_TEMPLATE["hinglish"] = (
    "{location} ka weather: {condition}, abhi {temp}°C (range {tmin}–{tmax}°C). "
    "Rain chance {rain_prob}% hai, wind {wind} km/h."
)
NO_LOCATION_PROMPT["hinglish"] = "Kis place ka weather chahiye? Location button bhi tap kar sakte ho."
LOCATION_NOT_FOUND["hinglish"] = "Ye place nahi mila. Spelling check karo ya nearby bada city try karo."
for _level in ALERT_LABEL.values():
    _level.setdefault("hinglish", _level.get("en", ""))

# ---------------------------------------------------------------------------
# Deterministic multilingual fallbacks used when no external LLM/translation
# API is configured. This guarantees that choosing a reply language changes
# the actual bot response, not only the UI labels.
# ---------------------------------------------------------------------------
GREETING = {
    "en": "Namaste! I'm WeatherGPT. Ask me about weather, forecasts, rain, AQI, alerts, routes, renewable energy, construction, farming, aviation or marine conditions.",
    "hinglish": "Namaste! Main WeatherGPT hoon. Weather, forecast, baarish, AQI, alerts, routes, renewable energy, construction, farming, aviation ya marine conditions ke baare mein poochho.",
    "hi": "नमस्ते! मैं WeatherGPT हूँ। मौसम, पूर्वानुमान, बारिश, AQI, चेतावनी, मार्ग, नवीकरणीय ऊर्जा, निर्माण, खेती, विमानन या समुद्री स्थिति के बारे में पूछिए।",
    "bn": "নমস্কার! আমি WeatherGPT। আবহাওয়া, পূর্বাভাস, বৃষ্টি, AQI, সতর্কতা, রুট, নবায়নযোগ্য শক্তি, নির্মাণ, কৃষি, বিমান চলাচল বা সামুদ্রিক পরিস্থিতি সম্পর্কে জিজ্ঞেস করুন।",
    "ta": "வணக்கம்! நான் WeatherGPT. வானிலை, முன்னறிவிப்பு, மழை, AQI, எச்சரிக்கை, பாதை, புதுப்பிக்கத்தக்க ஆற்றல், கட்டுமானம், வேளாண்மை, விமானம் அல்லது கடல் நிலை பற்றி கேளுங்கள்.",
    "te": "నమస్తే! నేను WeatherGPT. వాతావరణం, ముందస్తు అంచనా, వర్షం, AQI, హెచ్చరికలు, మార్గాలు, పునరుత్పాదక శక్తి, నిర్మాణం, వ్యవసాయం, విమానయానం లేదా సముద్ర పరిస్థితుల గురించి అడగండి.",
    "mr": "नमस्कार! मी WeatherGPT आहे. हवामान, अंदाज, पाऊस, AQI, इशारे, मार्ग, नवीकरणीय ऊर्जा, बांधकाम, शेती, विमान वाहतूक किंवा सागरी परिस्थितीबद्दल विचारा.",
    "gu": "નમસ્તે! હું WeatherGPT છું. હવામાન, આગાહી, વરસાદ, AQI, ચેતવણીઓ, માર્ગ, નવિનીકરણીય ઊર્જા, બાંધકામ, ખેતી, વિમાનન અથવા સમુદ્રી પરિસ્થિતિ વિશે પૂછો.",
    "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ WeatherGPT ਹਾਂ। ਮੌਸਮ, ਭਵਿੱਖਬਾਣੀ, ਮੀਂਹ, AQI, ਚੇਤਾਵਨੀਆਂ, ਰੂਟ, ਨਵੀਂਕਰਣਯੋਗ ਊਰਜਾ, ਨਿਰਮਾਣ, ਖੇਤੀ, ਹਵਾਈ ਯਾਤਰਾ ਜਾਂ ਸਮੁੰਦਰੀ ਹਾਲਾਤ ਬਾਰੇ ਪੁੱਛੋ।",
    "kn": "ನಮಸ್ಕಾರ! ನಾನು WeatherGPT. ಹವಾಮಾನ, ಮುನ್ಸೂಚನೆ, ಮಳೆ, AQI, ಎಚ್ಚರಿಕೆ, ಮಾರ್ಗ, ನವೀಕರಿಸಬಹುದಾದ ಶಕ್ತಿ, ನಿರ್ಮಾಣ, ಕೃಷಿ, ವಿಮಾನಯಾನ ಅಥವಾ ಸಮುದ್ರ ಪರಿಸ್ಥಿತಿಗಳ ಬಗ್ಗೆ ಕೇಳಿ.",
    "ml": "നമസ്കാരം! ഞാൻ WeatherGPT ആണ്. കാലാവസ്ഥ, പ്രവചനം, മഴ, AQI, മുന്നറിയിപ്പുകൾ, റൂട്ടുകൾ, പുനരുപയോഗ ഊർജം, നിർമ്മാണം, കൃഷി, വ്യോമയാനം അല്ലെങ്കിൽ സമുദ്രാവസ്ഥയെ കുറിച്ച് ചോദിക്കൂ.",
    "or": "ନମସ୍କାର! ମୁଁ WeatherGPT। ପାଣିପାଗ, ପୂର୍ବାନୁମାନ, ବର୍ଷା, AQI, ସତର୍କତା, ରୁଟ୍, ନବୀକରଣଯୋଗ୍ୟ ଶକ୍ତି, ନିର୍ମାଣ, କୃଷି, ବିମାନ ବା ସମୁଦ୍ର ଅବସ୍ଥା ବିଷୟରେ ପଚାରନ୍ତୁ।",
    "ur": "نمستے! میں WeatherGPT ہوں۔ موسم، پیش گوئی، بارش، AQI، انتباہات، راستے، قابلِ تجدید توانائی، تعمیرات، زراعت، ہوا بازی یا سمندری حالات کے بارے میں پوچھیں۔",
}

HELP = {
    "en": "Try: ‘weather in Kolkata’, ‘2 day forecast for Dhaka’, ‘will it rain tomorrow?’, ‘AQI near me’, or use the quick modules. You can name a place or share your GPS location.",
    "hinglish": "Try karo: ‘Kolkata ka weather’, ‘Dhaka ka 2 day forecast’, ‘kal baarish hogi?’, ‘mere paas AQI’, ya quick modules use karo. Place ka naam do ya GPS location share karo.",
    "hi": "उदाहरण: ‘कोलकाता का मौसम’, ‘ढाका का 2 दिन का पूर्वानुमान’, ‘कल बारिश होगी?’, ‘मेरे पास AQI’। आप स्थान का नाम दे सकते हैं या GPS लोकेशन साझा कर सकते हैं।",
    "bn": "উদাহরণ: ‘কলকাতার আবহাওয়া’, ‘ঢাকার ২ দিনের পূর্বাভাস’, ‘কাল বৃষ্টি হবে?’, ‘আমার কাছে AQI’। স্থানের নাম লিখুন বা GPS লোকেশন শেয়ার করুন।",
    "ta": "உதாரணம்: ‘கொல்கத்தா வானிலை’, ‘டாக்கா 2 நாள் முன்னறிவிப்பு’, ‘நாளை மழை வருமா?’, ‘என் அருகிலுள்ள AQI’. இடத்தை எழுதலாம் அல்லது GPS இருப்பிடத்தை பகிரலாம்.",
    "te": "ఉదాహరణ: ‘కోల్‌కతా వాతావరణం’, ‘ఢాకా 2 రోజుల అంచనా’, ‘రేపు వర్షం పడుతుందా?’, ‘నా దగ్గర AQI’. ప్రదేశం పేరు ఇవ్వండి లేదా GPS స్థానం పంచుకోండి.",
    "mr": "उदाहरण: ‘कोलकात्याचे हवामान’, ‘ढाकाचा 2 दिवसांचा अंदाज’, ‘उद्या पाऊस पडेल का?’, ‘माझ्या जवळचा AQI’. ठिकाणाचे नाव द्या किंवा GPS स्थान शेअर करा.",
    "gu": "ઉદાહરણ: ‘કોલકાતાનું હવામાન’, ‘ઢાકાનો 2 દિવસનો આગાહી’, ‘કાલે વરસાદ પડશે?’, ‘મારા નજીક AQI’. સ્થળનું નામ આપો અથવા GPS સ્થાન શેર કરો.",
    "pa": "ਉਦਾਹਰਨ: ‘ਕੋਲਕਾਤਾ ਦਾ ਮੌਸਮ’, ‘ਢਾਕਾ ਦੀ 2 ਦਿਨਾਂ ਦੀ ਭਵਿੱਖਬਾਣੀ’, ‘ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ?’, ‘ਮੇਰੇ ਨੇੜੇ AQI’। ਥਾਂ ਦਾ ਨਾਂ ਦਿਓ ਜਾਂ GPS ਸਥਾਨ ਸਾਂਝਾ ਕਰੋ।",
    "kn": "ಉದಾಹರಣೆ: ‘ಕೊಲ್ಕತ್ತಾ ಹವಾಮಾನ’, ‘ಢಾಕಾ 2 ದಿನಗಳ ಮುನ್ಸೂಚನೆ’, ‘ನಾಳೆ ಮಳೆ ಬರುತ್ತದೆಯೇ?’, ‘ನನ್ನ ಹತ್ತಿರ AQI’. ಸ್ಥಳದ ಹೆಸರು ನೀಡಿ ಅಥವಾ GPS ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ.",
    "ml": "ഉദാഹരണം: ‘കൊൽക്കത്തയിലെ കാലാവസ്ഥ’, ‘ഡാക്കയുടെ 2 ദിവസത്തെ പ്രവചനം’, ‘നാളെ മഴയുണ്ടാകുമോ?’, ‘എന്റെ അടുത്തുള്ള AQI’. സ്ഥലത്തിന്റെ പേര് നൽകുക അല്ലെങ്കിൽ GPS സ്ഥാനം പങ്കിടുക.",
    "or": "ଉଦାହରଣ: ‘କୋଲକାତା ପାଣିପାଗ’, ‘ଢାକା 2 ଦିନର ପୂର୍ବାନୁମାନ’, ‘କାଲି ବର୍ଷା ହେବ କି?’, ‘ମୋ ପାଖରେ AQI’। ସ୍ଥାନର ନାମ ଦିଅନ୍ତୁ କିମ୍ବା GPS ଲୋକେସନ୍ ଶେୟାର କରନ୍ତୁ।",
    "ur": "مثال: ‘کولکتہ کا موسم’، ‘ڈھاکہ کی 2 دن کی پیش گوئی’، ‘کل بارش ہوگی؟’، ‘میرے قریب AQI’۔ جگہ کا نام دیں یا GPS مقام شیئر کریں۔",
}

FORECAST_TEMPLATE = {
    "en": "{days}-day weather forecast for {location}. The requested {days} day(s) are shown below with temperature range, rain chance, rainfall, wind and weather condition.",
    "hinglish": "{location} ka {days}-day weather forecast. Neeche {days} din ka temperature range, rain chance, rainfall, wind aur weather condition diya hai.",
    "hi": "{location} का {days} दिन का मौसम पूर्वानुमान। नीचे {days} दिनों का तापमान, बारिश की संभावना, वर्षा, हवा और मौसम की स्थिति दी गई है।",
    "bn": "{location}-এর {days} দিনের আবহাওয়ার পূর্বাভাস। নিচে {days} দিনের তাপমাত্রার পরিসর, বৃষ্টির সম্ভাবনা, বৃষ্টিপাত, বাতাস ও আবহাওয়ার অবস্থা দেখানো হয়েছে।",
    "ta": "{location} இடத்திற்கான {days} நாள் வானிலை முன்னறிவிப்பு. கீழே {days} நாட்களின் வெப்பநிலை வரம்பு, மழை வாய்ப்பு, மழையளவு, காற்று மற்றும் வானிலை நிலை காட்டப்பட்டுள்ளது.",
    "te": "{location} కోసం {days} రోజుల వాతావరణ అంచనా. క్రింద {days} రోజుల ఉష్ణోగ్రత పరిధి, వర్షం అవకాశం, వర్షపాతం, గాలి మరియు వాతావరణ పరిస్థితి చూపబడింది.",
    "mr": "{location} साठी {days} दिवसांचा हवामान अंदाज. खाली {days} दिवसांचे तापमान, पावसाची शक्यता, पर्जन्यमान, वारा आणि हवामान स्थिती दाखवली आहे.",
    "gu": "{location} માટે {days} દિવસની હવામાન આગાહી. નીચે {days} દિવસનું તાપમાન, વરસાદની શક્યતા, વરસાદ, પવન અને હવામાન સ્થિતિ બતાવવામાં આવી છે.",
    "pa": "{location} ਲਈ {days} ਦਿਨਾਂ ਦੀ ਮੌਸਮ ਭਵਿੱਖਬਾਣੀ। ਹੇਠਾਂ {days} ਦਿਨਾਂ ਦਾ ਤਾਪਮਾਨ, ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ, ਵਰਖਾ, ਹਵਾ ਅਤੇ ਮੌਸਮੀ ਹਾਲਤ ਦਿੱਤੀ ਹੈ।",
    "kn": "{location} ಗೆ {days} ದಿನಗಳ ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ. ಕೆಳಗೆ {days} ದಿನಗಳ ತಾಪಮಾನ ವ್ಯಾಪ್ತಿ, ಮಳೆಯ ಸಾಧ್ಯತೆ, ಮಳೆ ಪ್ರಮಾಣ, ಗಾಳಿ ಮತ್ತು ಹವಾಮಾನ ಸ್ಥಿತಿ ನೀಡಲಾಗಿದೆ.",
    "ml": "{location} ലേക്കുള്ള {days} ദിവസത്തെ കാലാവസ്ഥ പ്രവചനം. താഴെ {days} ദിവസത്തെ താപനില പരിധി, മഴ സാധ്യത, മഴയുടെ അളവ്, കാറ്റ്, കാലാവസ്ഥ സ്ഥിതി എന്നിവ കാണിക്കുന്നു.",
    "or": "{location} ପାଇଁ {days} ଦିନର ପାଣିପାଗ ପୂର୍ବାନୁମାନ। ତଳେ {days} ଦିନର ତାପମାତ୍ରା, ବର୍ଷା ସମ୍ଭାବନା, ବର୍ଷା ପରିମାଣ, ପବନ ଏବଂ ପାଣିପାଗ ଅବସ୍ଥା ଦିଆଯାଇଛି।",
    "ur": "{location} کے لیے {days} دن کی موسم کی پیش گوئی۔ نیچے {days} دن کا درجۂ حرارت، بارش کا امکان، بارش کی مقدار، ہوا اور موسمی حالت دکھائی گئی ہے۔",
}

AQI_TEMPLATE = {
    "en": "Air quality in {location}: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "hinglish": "{location} ki air quality: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "hi": "{location} की वायु गुणवत्ता: AQI {aqi} — {category}। PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³।",
    "bn": "{location}-এর বায়ুর মান: AQI {aqi} — {category}। PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³।",
    "ta": "{location} காற்றுத் தரம்: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "te": "{location} గాలి నాణ్యత: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "mr": "{location} ची हवा गुणवत्ता: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "gu": "{location} ની હવા ગુણવત્તા: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "pa": "{location} ਦੀ ਹਵਾ ਗੁਣਵੱਤਾ: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "kn": "{location} ಗಾಳಿ ಗುಣಮಟ್ಟ: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "ml": "{location} ലെ വായു ഗുണനിലവാരം: AQI {aqi} — {category}. PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³.",
    "or": "{location} ର ବାୟୁ ଗୁଣବତ୍ତା: AQI {aqi} — {category}। PM2.5 {pm25} µg/m³, PM10 {pm10} µg/m³।",
    "ur": "{location} کی ہوا کا معیار: AQI {aqi} — {category}۔ PM2.5 {pm25} µg/m³، PM10 {pm10} µg/m³۔",
}

_GENERIC = {
    "en": "{topic} for {location}: temperature {temp}°C, rain chance {rain}%, wind {wind} km/h, alert {alert}.",
    "hinglish": "{location} ke liye {topic}: temperature {temp}°C, rain chance {rain}%, wind {wind} km/h, alert {alert}.",
    "hi": "{location} के लिए {topic}: तापमान {temp}°C, बारिश की संभावना {rain}%, हवा {wind} किमी/घंटा, चेतावनी {alert}।",
    "bn": "{location}-এর জন্য {topic}: তাপমাত্রা {temp}°সে, বৃষ্টির সম্ভাবনা {rain}%, বাতাস {wind} কিমি/ঘণ্টা, সতর্কতা {alert}।",
    "ta": "{location} இடத்திற்கான {topic}: வெப்பநிலை {temp}°C, மழை வாய்ப்பு {rain}%, காற்று {wind} கிமீ/மணி, எச்சரிக்கை {alert}.",
    "te": "{location} కోసం {topic}: ఉష్ణోగ్రత {temp}°C, వర్షం అవకాశం {rain}%, గాలి {wind} కి.మీ/గం, హెచ్చరిక {alert}.",
    "mr": "{location} साठी {topic}: तापमान {temp}°C, पावसाची शक्यता {rain}%, वारा {wind} किमी/तास, इशारा {alert}.",
    "gu": "{location} માટે {topic}: તાપમાન {temp}°C, વરસાદની શક્યતા {rain}%, પવન {wind} કિમી/કલાક, ચેતવણી {alert}.",
    "pa": "{location} ਲਈ {topic}: ਤਾਪਮਾਨ {temp}°C, ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ {rain}%, ਹਵਾ {wind} ਕਿਮੀ/ਘੰਟਾ, ਚੇਤਾਵਨੀ {alert}।",
    "kn": "{location} ಗೆ {topic}: ತಾಪಮಾನ {temp}°C, ಮಳೆಯ ಸಾಧ್ಯತೆ {rain}%, ಗಾಳಿ {wind} ಕಿಮೀ/ಗಂ, ಎಚ್ಚರಿಕೆ {alert}.",
    "ml": "{location} ലേക്കുള്ള {topic}: താപനില {temp}°C, മഴ സാധ്യത {rain}%, കാറ്റ് {wind} കി.മീ/മണിക്കൂർ, മുന്നറിയിപ്പ് {alert}.",
    "or": "{location} ପାଇଁ {topic}: ତାପମାତ୍ରା {temp}°C, ବର୍ଷା ସମ୍ଭାବନା {rain}%, ପବନ {wind} କିମି/ଘଣ୍ଟା, ସତର୍କତା {alert}।",
    "ur": "{location} کے لیے {topic}: درجۂ حرارت {temp}°C، بارش کا امکان {rain}%، ہوا {wind} کلومیٹر/گھنٹہ، انتباہ {alert}۔",
}

TOPIC = {
    "agriculture": {"en":"farm advisory","hinglish":"farm advisory","hi":"कृषि सलाह","bn":"কৃষি পরামর্শ","ta":"வேளாண் ஆலோசனை","te":"వ్యవసాయ సలహా","mr":"कृषी सल्ला","gu":"કૃષિ સલાહ","pa":"ਖੇਤੀ ਸਲਾਹ","kn":"ಕೃಷಿ ಸಲಹೆ","ml":"കൃഷി ഉപദേശം","or":"କୃଷି ପରାମର୍ଶ","ur":"زرعی مشورہ"},
    "aviation": {"en":"aviation briefing","hinglish":"aviation briefing","hi":"विमानन ब्रीफिंग","bn":"বিমান চলাচল ব্রিফিং","ta":"விமானப் பயண அறிவுரை","te":"విమానయాన సమాచారం","mr":"विमान वाहतूक माहिती","gu":"વિમાનન માહિતી","pa":"ਹਵਾਈ ਯਾਤਰਾ ਜਾਣਕਾਰੀ","kn":"ವಿಮಾನಯಾನ ಮಾಹಿತಿ","ml":"വ്യോമയാന വിവരം","or":"ବିମାନ ଚଳାଚଳ ସୂଚନା","ur":"ہوا بازی بریفنگ"},
    "marine": {"en":"marine advisory","hinglish":"marine advisory","hi":"समुद्री सलाह","bn":"সামুদ্রিক পরামর্শ","ta":"கடல் ஆலோசனை","te":"సముద్ర సలహా","mr":"सागरी सल्ला","gu":"સમુદ્રી સલાહ","pa":"ਸਮੁੰਦਰੀ ਸਲਾਹ","kn":"ಸಮುದ್ರ ಸಲಹೆ","ml":"സമുദ്ര ഉപദേശം","or":"ସମୁଦ୍ର ପରାମର୍ଶ","ur":"سمندری مشورہ"},
    "urban": {"en":"city advisory","hinglish":"city advisory","hi":"शहरी सलाह","bn":"শহর পরামর্শ","ta":"நகர ஆலோசனை","te":"నగర సలహా","mr":"शहर सल्ला","gu":"શહેર સલાહ","pa":"ਸ਼ਹਿਰੀ ਸਲਾਹ","kn":"ನಗರ ಸಲಹೆ","ml":"നഗര ഉപദേശം","or":"ସହର ପରାମର୍ଶ","ur":"شہری مشورہ"},
    "energy": {"en":"renewable-energy outlook","hinglish":"renewable-energy outlook","hi":"नवीकरणीय ऊर्जा पूर्वानुमान","bn":"নবায়নযোগ্য শক্তির পূর্বাভাস","ta":"புதுப்பிக்கத்தக்க ஆற்றல் முன்னறிவிப்பு","te":"పునరుత్పాదక శక్తి అంచనా","mr":"नवीकरणीय ऊर्जा अंदाज","gu":"નવિનીકરણીય ઊર્જા આગાહી","pa":"ਨਵੀਂਕਰਣਯੋਗ ਊਰਜਾ ਅਨੁਮਾਨ","kn":"ನವೀಕರಿಸಬಹುದಾದ ಶಕ್ತಿ ಮುನ್ಸೂಚನೆ","ml":"പുനരുപയോഗ ഊർജ പ്രവചനം","or":"ନବୀକରଣଯୋଗ୍ୟ ଶକ୍ତି ପୂର୍ବାନୁମାନ","ur":"قابلِ تجدید توانائی کی پیش گوئی"},
    "retail": {"en":"retail and inventory advisory","hinglish":"retail aur inventory advisory","hi":"रिटेल और इन्वेंटरी सलाह","bn":"রিটেল ও ইনভেন্টরি পরামর্শ","ta":"சில்லறை மற்றும் இருப்பு ஆலோசனை","te":"రిటైల్ మరియు ఇన్వెంటరీ సలహా","mr":"रिटेल व इन्व्हेंटरी सल्ला","gu":"રીટેલ અને ઇન્વેન્ટરી સલાહ","pa":"ਰੀਟੇਲ ਅਤੇ ਇਨਵੈਂਟਰੀ ਸਲਾਹ","kn":"ರಿಟೇಲ್ ಮತ್ತು ಇನ್‌ವೆಂಟರಿ ಸಲಹೆ","ml":"റീട്ടെയിൽ, ഇൻവെന്ററി ഉപദേശം","or":"ରିଟେଲ୍ ଏବଂ ଇନଭେଣ୍ଟୋରି ପରାମର୍ଶ","ur":"ریٹیل اور انوینٹری مشورہ"},
    "construction": {"en":"construction contingency","hinglish":"construction contingency","hi":"निर्माण आकस्मिक योजना","bn":"নির্মাণ জরুরি পরিকল্পনা","ta":"கட்டுமான அவசரத் திட்டம்","te":"నిర్మాణ ప్రత్యామ్నాయ ప్రణాళిక","mr":"बांधकाम आकस्मिक योजना","gu":"બાંધકામ કન્ટિજેન્સી","pa":"ਨਿਰਮਾਣ ਐਮਰਜੈਂਸੀ ਯੋਜਨਾ","kn":"ನಿರ್ಮಾಣ ತುರ್ತು ಯೋಜನೆ","ml":"നിർമ്മാണ അടിയന്തര പദ്ധതി","or":"ନିର୍ମାଣ ଆପତ୍କାଳୀନ ଯୋଜନା","ur":"تعمیراتی ہنگامی منصوبہ"},
}

def generic_weather_summary(intent: str, lang: str, *, location: str, temp, rain, wind, alert: str) -> str:
    lang = lang if lang in SUPPORTED else "en"
    topic = TOPIC.get(intent, {}).get(lang) or TOPIC.get(intent, {}).get("en") or intent
    return t(_GENERIC, lang).format(location=location, topic=topic, temp=temp, rain=rain, wind=wind, alert=alert)

_CONDITION_GROUPS = {
    "clear": {0,1}, "cloudy": {2,3}, "fog": {45,48}, "drizzle": {51,53,55,56,57},
    "rain": {61,63,65,66,67,80,81,82}, "snow": {71,73,75,77,85,86}, "storm": {95,96,99},
}
_CONDITIONS = {
    "en": {"clear":"clear sky","cloudy":"cloudy","fog":"fog","drizzle":"drizzle","rain":"rain","snow":"snow","storm":"thunderstorm","other":"changeable conditions"},
    "hinglish": {"clear":"saaf aasman","cloudy":"badal chhaye hue","fog":"kohra","drizzle":"halki boondabandi","rain":"baarish","snow":"barfbaari","storm":"garaj-chamak wala tufaan","other":"badalta weather"},
    "hi": {"clear":"साफ आसमान","cloudy":"बादल छाए हुए","fog":"कोहरा","drizzle":"हल्की बूंदाबांदी","rain":"बारिश","snow":"बर्फबारी","storm":"गरज-चमक वाला तूफान","other":"बदलता मौसम"},
    "bn": {"clear":"পরিষ্কার আকাশ","cloudy":"মেঘলা","fog":"কুয়াশা","drizzle":"গুঁড়ি গুঁড়ি বৃষ্টি","rain":"বৃষ্টি","snow":"তুষারপাত","storm":"বজ্রঝড়","other":"পরিবর্তনশীল আবহাওয়া"},
    "ta": {"clear":"தெளிந்த வானம்","cloudy":"மேகமூட்டம்","fog":"மூடுபனி","drizzle":"தூறல்","rain":"மழை","snow":"பனிப்பொழிவு","storm":"இடியுடன் கூடிய மழை","other":"மாறக்கூடிய வானிலை"},
    "te": {"clear":"స్పష్టమైన ఆకాశం","cloudy":"మేఘావృతం","fog":"పొగమంచు","drizzle":"చినుకులు","rain":"వర్షం","snow":"మంచు","storm":"ఉరుములతో కూడిన వర్షం","other":"మారే వాతావరణం"},
    "mr": {"clear":"स्वच्छ आकाश","cloudy":"ढगाळ","fog":"धुके","drizzle":"रिमझिम","rain":"पाऊस","snow":"हिमवर्षाव","storm":"वादळी पाऊस","other":"बदलते हवामान"},
    "gu": {"clear":"સ્વચ્છ આકાશ","cloudy":"વાદળછાયું","fog":"ધુમ્મસ","drizzle":"ઝરમર વરસાદ","rain":"વરસાદ","snow":"હિમવર્ષા","storm":"વીજળી સાથે તોફાન","other":"બદલાતું હવામાન"},
    "pa": {"clear":"ਸਾਫ਼ ਆਸਮਾਨ","cloudy":"ਬੱਦਲਵਾਈ","fog":"ਧੁੰਦ","drizzle":"ਹਲਕੀ ਫੁਹਾਰ","rain":"ਮੀਂਹ","snow":"ਬਰਫ਼ਬਾਰੀ","storm":"ਗਰਜ-ਚਮਕ ਵਾਲਾ ਤੂਫ਼ਾਨ","other":"ਬਦਲਦਾ ਮੌਸਮ"},
    "kn": {"clear":"ಸ್ವಚ್ಛ ಆಕಾಶ","cloudy":"ಮೋಡ ಕವಿದ","fog":"ಮಂಜು","drizzle":"ತುಂತುರು ಮಳೆ","rain":"ಮಳೆ","snow":"ಹಿಮಪಾತ","storm":"ಗುಡುಗು ಮಳೆ","other":"ಬದಲಾಗುವ ಹವಾಮಾನ"},
    "ml": {"clear":"തെളിഞ്ഞ ആകാശം","cloudy":"മേഘാവൃതം","fog":"മൂടൽമഞ്ഞ്","drizzle":"ചാറ്റൽമഴ","rain":"മഴ","snow":"മഞ്ഞുവീഴ്ച","storm":"ഇടിമിന്നലോട് കൂടിയ മഴ","other":"മാറിക്കൊണ്ടിരിക്കുന്ന കാലാവസ്ഥ"},
    "or": {"clear":"ସ୍ପଷ୍ଟ ଆକାଶ","cloudy":"ମେଘାଚ୍ଛନ୍ନ","fog":"କୁହୁଡ଼ି","drizzle":"ଝିପିଝିପି ବର୍ଷା","rain":"ବର୍ଷା","snow":"ତୁଷାରପାତ","storm":"ବଜ୍ରପାତ ସହ ବର୍ଷା","other":"ପରିବର୍ତ୍ତନଶୀଳ ପାଣିପାଗ"},
    "ur": {"clear":"صاف آسمان","cloudy":"ابر آلود","fog":"دھند","drizzle":"ہلکی پھوار","rain":"بارش","snow":"برف باری","storm":"گرج چمک کے ساتھ طوفان","other":"بدلتا موسم"},
}

def weather_condition(code, lang: str) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        c = -1
    group = next((name for name, codes in _CONDITION_GROUPS.items() if c in codes), "other")
    table = _CONDITIONS.get(lang, _CONDITIONS["en"])
    return table.get(group, table["other"])

RAIN_TEMPLATE = {
    "en": "Rain chance for {location} {when}: {rain}%. {advice}",
    "hinglish": "{location} mein {when} rain chance {rain}% hai. {advice}",
    "hi": "{location} में {when} बारिश की संभावना {rain}% है। {advice}",
    "bn": "{location}-এ {when} বৃষ্টির সম্ভাবনা {rain}%। {advice}",
    "ta": "{location} இல் {when} மழை வாய்ப்பு {rain}%. {advice}",
    "te": "{location}లో {when} వర్షం అవకాశం {rain}%. {advice}",
    "mr": "{location} येथे {when} पावसाची शक्यता {rain}% आहे. {advice}",
    "gu": "{location} માં {when} વરસાદની શક્યતા {rain}% છે. {advice}",
    "pa": "{location} ਵਿੱਚ {when} ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ {rain}% ਹੈ। {advice}",
    "kn": "{location} ನಲ್ಲಿ {when} ಮಳೆಯ ಸಾಧ್ಯತೆ {rain}%. {advice}",
    "ml": "{location} ൽ {when} മഴയ്ക്കുള്ള സാധ്യത {rain}% ആണ്. {advice}",
    "or": "{location} ରେ {when} ବର୍ଷାର ସମ୍ଭାବନା {rain}%। {advice}",
    "ur": "{location} میں {when} بارش کا امکان {rain}% ہے۔ {advice}",
}
WHEN = {
    "today":{"en":"today","hinglish":"aaj","hi":"आज","bn":"আজ","ta":"இன்று","te":"ఈరోజు","mr":"आज","gu":"આજે","pa":"ਅੱਜ","kn":"ಇಂದು","ml":"ഇന്ന്","or":"ଆଜି","ur":"آج"},
    "tomorrow":{"en":"tomorrow","hinglish":"kal","hi":"कल","bn":"আগামীকাল","ta":"நாளை","te":"రేపు","mr":"उद्या","gu":"કાલે","pa":"ਕੱਲ੍ਹ","kn":"ನಾಳೆ","ml":"നാളെ","or":"କାଲି","ur":"کل"},
}
RAIN_ADVICE_YES = {"en":"Carry an umbrella or raincoat.","hinglish":"Umbrella ya raincoat le jao.","hi":"छाता या रेनकोट साथ रखें।","bn":"ছাতা বা রেইনকোট সঙ্গে রাখুন।","ta":"குடை அல்லது மழைக்கோட் எடுத்துச் செல்லுங்கள்.","te":"గొడుగు లేదా రైన్‌కోట్ తీసుకెళ్లండి.","mr":"छत्री किंवा रेनकोट सोबत ठेवा.","gu":"છત્રી અથવા રેઇનકોટ સાથે રાખો.","pa":"ਛਤਰੀ ਜਾਂ ਰੇਨਕੋਟ ਨਾਲ ਰੱਖੋ।","kn":"ಛತ್ರಿ ಅಥವಾ ರೇನ್‌ಕೋಟ್ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ.","ml":"കുടയോ മഴക്കോട്ടോ കരുതുക.","or":"ଛତା କିମ୍ବା ରେନକୋଟ୍ ସହିତ ନିଅନ୍ତୁ।","ur":"چھتری یا رین کوٹ ساتھ رکھیں۔"}
RAIN_ADVICE_NO = {"en":"An umbrella is probably not needed.","hinglish":"Umbrella shayad zaroori nahi hai.","hi":"छाते की शायद जरूरत नहीं है।","bn":"সম্ভবত ছাতার প্রয়োজন হবে না।","ta":"குடை பெரும்பாலும் தேவையில்லை.","te":"గొడుగు బహుశా అవసరం లేదు.","mr":"छत्रीची बहुधा गरज नाही.","gu":"છત્રીની કદાચ જરૂર નહીં પડે.","pa":"ਛਤਰੀ ਦੀ ਸ਼ਾਇਦ ਲੋੜ ਨਹੀਂ ਪਵੇਗੀ।","kn":"ಛತ್ರಿ ಬಹುಶಃ ಅಗತ್ಯವಿಲ್ಲ.","ml":"കുട സാധാരണയായി ആവശ്യമില്ല.","or":"ସମ୍ଭବତଃ ଛତା ଦରକାର ହେବ ନାହିଁ।","ur":"چھتری کی غالباً ضرورت نہیں ہوگی۔"}

ALERT_TEMPLATE = {
    "en":"Weather alert for {location}: {alert}.","hinglish":"{location} ka weather alert: {alert}.","hi":"{location} के लिए मौसम चेतावनी: {alert}।","bn":"{location}-এর আবহাওয়া সতর্কতা: {alert}।","ta":"{location} வானிலை எச்சரிக்கை: {alert}.","te":"{location} వాతావరణ హెచ్చరిక: {alert}.","mr":"{location} साठी हवामान इशारा: {alert}.","gu":"{location} માટે હવામાન ચેતવણી: {alert}.","pa":"{location} ਲਈ ਮੌਸਮ ਚੇਤਾਵਨੀ: {alert}।","kn":"{location} ಹವಾಮಾನ ಎಚ್ಚರಿಕೆ: {alert}.","ml":"{location} ലെ കാലാവസ്ഥ മുന്നറിയിപ്പ്: {alert}.","or":"{location} ପାଇଁ ପାଣିପାଗ ସତର୍କତା: {alert}।","ur":"{location} کے لیے موسمی انتباہ: {alert}۔"
}
CLIMATE_TEMPLATE = {
    "en":"10-year climate trend for {location} is ready. The chart below shows annual average maximum temperature and rainfall.","hinglish":"{location} ka 10-year climate trend ready hai. Neeche chart mein yearly average maximum temperature aur rainfall dikhaya hai.","hi":"{location} का 10-वर्षीय जलवायु रुझान तैयार है। नीचे चार्ट में वार्षिक औसत अधिकतम तापमान और वर्षा दिखाई गई है।","bn":"{location}-এর ১০ বছরের জলবায়ু প্রবণতা প্রস্তুত। নিচের চার্টে বার্ষিক গড় সর্বোচ্চ তাপমাত্রা ও বৃষ্টিপাত দেখানো হয়েছে।","ta":"{location} இடத்தின் 10 ஆண்டு காலநிலை போக்கு தயாராக உள்ளது. கீழே ஆண்டுதோறும் சராசரி அதிகபட்ச வெப்பநிலை மற்றும் மழை காட்டப்பட்டுள்ளது.","te":"{location} యొక్క 10 సంవత్సరాల వాతావరణ ధోరణి సిద్ధంగా ఉంది. క్రింద వార్షిక సగటు గరిష్ఠ ఉష్ణోగ్రత మరియు వర్షపాతం చూపబడింది.","mr":"{location} चा 10 वर्षांचा हवामान कल तयार आहे. खाली वार्षिक सरासरी कमाल तापमान आणि पर्जन्यमान दाखवले आहे.","gu":"{location} નો 10 વર્ષનો આબોહવા ટ્રેન્ડ તૈયાર છે. નીચે વાર્ષિક સરેરાશ મહત્તમ તાપમાન અને વરસાદ બતાવ્યો છે.","pa":"{location} ਦਾ 10 ਸਾਲਾਂ ਦਾ ਜਲਵਾਯੂ ਰੁਝਾਨ ਤਿਆਰ ਹੈ। ਹੇਠਾਂ ਸਾਲਾਨਾ ਔਸਤ ਵੱਧ ਤੋਂ ਵੱਧ ਤਾਪਮਾਨ ਅਤੇ ਵਰਖਾ ਦਿਖਾਈ ਹੈ।","kn":"{location} ನ 10 ವರ್ಷದ ಹವಾಮಾನ ಪ್ರವೃತ್ತಿ ಸಿದ್ಧವಾಗಿದೆ. ಕೆಳಗಿನ ಚಾರ್ಟ್‌ನಲ್ಲಿ ವಾರ್ಷಿಕ ಸರಾಸರಿ ಗರಿಷ್ಠ ತಾಪಮಾನ ಮತ್ತು ಮಳೆ ತೋರಿಸಲಾಗಿದೆ.","ml":"{location} ലെ 10 വർഷത്തെ കാലാവസ്ഥ പ്രവണത തയ്യാറാണ്. താഴെയുള്ള ചാർട്ടിൽ വാർഷിക ശരാശരി പരമാവധി താപനിലയും മഴയും കാണിക്കുന്നു.","or":"{location} ର 10 ବର୍ଷର ଜଳବାୟୁ ପ୍ରବଣତା ପ୍ରସ୍ତୁତ। ତଳେ ବାର୍ଷିକ ହାରାହାରି ସର୍ବାଧିକ ତାପମାତ୍ରା ଏବଂ ବର୍ଷା ଦେଖାଯାଇଛି।","ur":"{location} کا 10 سالہ موسمی رجحان تیار ہے۔ نیچے سالانہ اوسط زیادہ سے زیادہ درجۂ حرارت اور بارش دکھائی گئی ہے۔"
}
