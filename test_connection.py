import requests
import time

# TMDB API kaliti (bu yerga o'zingizning API kalitingizni qo'ying)
TMDB_API_KEY = "3e9ee14df29848352d933f5850da2dc0"
URL_TMDB = "https://api.themoviedb.org/3"
movie_name = 'temir odam'

# Telegram server manzili
URL_TELEGRAM = "https://api.telegram.org"

print("--- Test boshlandi ---")

# 1-qadam: TMDB serveriga ulanishni tekshirish
try:
    print(f"\n[1-QADAM] TMDB serveriga ulanish tekshirilmoqda ({URL_TMDB})...")
    response1 = requests.get(URL_TMDB, timeout=10)
    print(f"✅ Muvaffaqiyatli! Status kodi: {response1.status_code}")
except Exception as e:
    print(f"❌ XATOLIK: TMDB serveriga ulanib bo'lmadi. Muammo: {e}")
    exit()

print("\nBir soniya kutilmoqda...")
time.sleep(1)

# 2-qadam: Telegram serveriga ulanishni tekshirish
try:
    print(f"\n[2-QADAM] Telegram serveriga ulanish tekshirilmoqda ({URL_TELEGRAM})...")
    response2 = requests.get(URL_TELEGRAM, timeout=10)
    print(f"✅ Muvaffaqiyatli! Status kodi: {response2.status_code}")
except Exception as e:
    print(f"\n❌ XATOLIK: Telegram serveriga ulanib bo'lmadi!")
    print(f"Sabab: {e}")

print("\n" + "="*50)
print("FILM QIDIRUV BO'LIMI")
print("="*50)

# 3-qadam: TMDB da film qidirish
if TMDB_API_KEY == "SIZNING_API_KALITINGIZ":
    print(f"\n⚠️  OGOHLANTIRISH: API kalit kiritilmagan!")
    print("TMDB dan film qidirish uchun API kalit kerak.")
    print("API kalitni https://www.themoviedb.org/ saytidan oling")
else:
    try:
        print(f"\n[3-QADAM] '{movie_name}' filmini qidirilmoqda...")

        # Film qidiruv so'rovi
        search_url = f"{URL_TMDB}/search/movie"
        params = {
            'api_key': TMDB_API_KEY,
            'query': movie_name,
            'language': 'uz-UZ'  # O'zbek tili uchun
        }

        search_response = requests.get(search_url, params=params, timeout=10)

        if search_response.status_code == 200:
            data = search_response.json()
            results = data.get('results', [])

            print(f"✅ Qidiruv muvaffaqiyatli! Topilgan filmlar soni: {len(results)}")

            if results:
                print(f"\n🎬 '{movie_name}' ga mos kelgan filmlar:")
                print("-" * 60)

                for i, movie in enumerate(results[:5], 1):  # Faqat birinchi 5 ta natijani ko'rsatish
                    title = movie.get('title', 'Noma\'lum')
                    original_title = movie.get('original_title', '')
                    release_date = movie.get('release_date', 'Noma\'lum sana')
                    overview = movie.get('overview', 'Tavsif mavjud emas')
                    rating = movie.get('vote_average', 0)

                    print(f"{i}. Nomi: {title}")
                    if original_title != title:
                        print(f"   Original nomi: {original_title}")
                    print(f"   Chiqarilgan sana: {release_date}")
                    print(f"   Reyting: {rating}/10")
                    print(f"   Qisqacha: {overview[:100]}..." if len(overview) > 100 else f"   Qisqacha: {overview}")
                    print("-" * 60)
            else:
                print(f"\n❌ '{movie_name}' nomli film topilmadi.")
                print("Boshqa nom bilan qidirib ko'ring.")

        else:
            print(f"❌ Qidiruv xatosi! Status kodi: {search_response.status_code}")

    except Exception as e:
        print(f"\n❌ Film qidirishda xatolik: {e}")

print("\n--- Test yakunlandi ---")

# Qo'shimcha ma'lumot
print(f"\n📋 MA'LUMOT:")
print(f"• Qidirilgan film: {movie_name}")
print(f"• TMDB API versiyasi: v3")
print(f"• Til: O'zbek")
