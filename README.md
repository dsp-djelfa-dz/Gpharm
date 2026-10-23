# Gpharm — Système de Gestion des Gardes de Pharmacies (DSP.DJELFA)

Système électronique de gestion du tableau de garde (nuit & jours fériés) des pharmacies de la wilaya de Djelfa.

## 📖 Documentation / الدليل

| Langue | Documentation |
|--------|---------------|
| 🇫🇷 Français | [docs/Guide_utilisation_Gpharm.pdf](docs/Guide_utilisation_Gpharm.pdf) |
| 🇩🇿 العربية | [docs/كتيب_شرح_الاستخدام_Gpharm.pdf](docs/كتيب_شرح_الاستخدام_Gpharm.pdf) |

Identifiants par défaut : `admin` / `admin123` (à changer dès la première utilisation).

## ✨ Fonctionnalités

- Gestion des daïras et des communes
- Gestion des pharmaciens et de leurs officines (import Excel supporté)
- Ordre de rotation pour une répartition équitable des gardes
- Gestion des absences (vacances)
- Génération automatique des tableaux de garde (rotation, vacances, vendredis & fériés)
- Impression PDF officielle (par daïra ou pour toutes les daïras)
- Interface d'administration protégée par connexion (Flask-Login)
- Base de données : Google Cloud Firestore

## 🚀 Lancer localement

```bash
pip install -r requirements.txt
# Configurer les clés Firebase (voir .env.example)
python app.py
# http://127.0.0.1:5000
```

## ☁️ Déploiement (Render)

Le fichier `render.yaml` est prêt. Définir les variables :
- `SECRET_KEY`
- `FIREBASE_CREDENTIALS_JSON`

## 🪟 Version Windows

Exécuter `build.bat` → `dist\PharmacyRoster.exe`

---

## النظام بالعربية

تطبيق Gpharm هو نظام إلكتروني لإدارة مناوبات صيدليات ولاية الجلفة (المناوبة الليلية والمناوبة النهارية في أيام الجمعة والأعياد)، يسمح بتسجيل الدوائر والبلديات والصيادلة والإجازات، ثم توليد جدول المناوبة آلياً وطباعته في ملف PDF رسمي.

دليل الاستخدام بالعربية في [docs/كتيب_شرح_الاستخدام_Gpharm.pdf](docs/كتيب_شرح_الاستخدام_Gpharm.pdf).

## Tech Stack

Python · Flask · Flask-Login · Google Cloud Firestore · fpdf2 · pandas · Bootstrap-free custom front-end
