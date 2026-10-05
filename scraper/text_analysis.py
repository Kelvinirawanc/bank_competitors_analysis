"""Transparent baseline text classification for Indonesian/mixed app reviews."""
import re

POSITIVE_WORDS = {
    "bagus","baik","mantap","keren","mudah","cepat","praktis","nyaman","suka","lancar",
    "stabil","terbaik","good","great","fast","easy","helpful","recommended","recommend",
    "nice","smooth","lengkap","aman","puas","memuaskan","perfect"
}
NEGATIVE_WORDS = {
    "error","gagal","lambat","lemot","pending","bug","crash","rusak","parah","susah","sulit",
    "kecewa","buruk","jelek","tidak bisa","nggak bisa","ga bisa","gak bisa","hang","freeze",
    "logout","blocked","macet","hilang","terpotong","komplain","complaint","bad","worst","slow",
    "failed","failure","cannot"
}
TOPICS = {
    "Login & KYC":["login","log in","masuk","otp","pin","password","biometric","biometrik","verifikasi","verification","kyc","daftar","registrasi","register","akun"],
    "Transaction":["transfer","transaksi","transaction","qr","qris","payment","pembayaran","top up","topup","tarik tunai","withdraw","settlement","mutasi","saldo"],
    "Customer Service":["cs","customer service","customer support","call center","komplain","complaint","respons","respon","dibalas","support"],
    "Performance & Bugs":["error","bug","crash","loading","lemot","lambat","hang","freeze","blank","force close","tidak bisa dibuka","update"],
    "Promo & Benefits":["promo","cashback","cash back","voucher","diskon","discount","bunga","interest","bonus","hadiah","paylater","pay later"],
    "UI / UX":["tampilan","interface","ui","ux","desain","design","menu","navigasi","navigation","fitur","feature","mudah digunakan"],
    "Security":["security","keamanan","fraud","penipuan","suspicious","blokir","blocked","otp","pin","rekening dibobol"],
    "Fees & Limits":["biaya","fee","admin","charge","limit","minimum","maksimum","gratis","free"],
}
ISSUES = {
    "Transfer failure / pending":["transfer gagal","transfer failed","transfer pending","pending","gagal transfer"],
    "Login / OTP":["login","otp","tidak bisa masuk","gagal login","otp tidak masuk"],
    "App error / crash":["error","crash","force close","blank","bug","hang","freeze"],
    "Verification / KYC":["verifikasi","verification","kyc","registrasi","daftar akun"],
    "Customer service response":["customer service","customer support","cs","komplain","complaint","tidak dibalas"],
    "Top up / payment":["top up","topup","pembayaran","payment","qris"],
    "Balance / refund":["saldo","refund","dana kembali","uang kembali","balance"],
    "Fees / charges":["biaya","admin","fee","charge","potongan"],
    "Promo / cashback":["promo","cashback","voucher","diskon"],
}

def normalize_text(text):
    text = (text or "").lower().strip()
    return re.sub(r"\s+", " ", text)

def _score(text, words):
    return sum(1 for word in words if word in text)

def classify_sentiment(text, rating):
    t = normalize_text(text)
    pos, neg = _score(t, POSITIVE_WORDS), _score(t, NEGATIVE_WORDS)
    if rating <= 2:
        return "Negative", round(min(.99, .80 + .05*min(3,neg)), 2)
    if rating >= 4:
        return "Positive", round(min(.99, .80 + .05*min(3,pos)), 2)
    if neg > pos:
        return "Negative", .68
    if pos > neg:
        return "Positive", .68
    return "Neutral", .72

def classify_topic(text):
    t = normalize_text(text)
    scores = [(sum(1 for w in words if w in t), topic) for topic, words in TOPICS.items()]
    best_score, best_topic = max(scores, key=lambda x:(x[0],x[1]))
    if best_score == 0:
        return "General", .55
    return best_topic, round(min(.98, .68 + .08*min(4,best_score)), 2)

def classify_issue(text):
    t = normalize_text(text)
    best_issue, best_score = "General", 0
    for issue, words in ISSUES.items():
        score = sum(1 for w in words if w in t)
        if score > best_score:
            best_issue, best_score = issue, score
    return best_issue

def validate_review(review):
    rating = review.get("rating")
    text = normalize_text(review.get("review_text", ""))
    checks = {
        "rating_valid": isinstance(rating, int) and 1 <= rating <= 5,
        "date_present": bool(review.get("review_date")),
        "review_id_present": bool(review.get("review_id")),
        "text_present": bool(text),
        "reasonable_text_length": len(text) >= 8 if text else False,
    }
    quality = int(sum(checks.values())/len(checks)*100)
    return {
        "validation_passed": checks["rating_valid"] and checks["date_present"] and checks["review_id_present"],
        "quality_score": quality,
        "actionable": bool(text) and len(text) >= 12,
        "validation_checks": checks,
    }
