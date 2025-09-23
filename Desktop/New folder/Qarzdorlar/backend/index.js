// ==========================================================
// 1. KUTUBXONALARNI VA SOZLAMALARNI BIR JOYGA YIG'ISH
// ==========================================================
require('dotenv').config();
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const cron = require('node-cron');
const db = require('./db');
const express = require('express');
const cors = require('cors');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');


const SECRET_KEY = process.env.BILLZ_SECRET_KEY;
const ALL_SHOPS = process.env.ALL_SHOPS;
const API_BASE_URL = "https://api-admin.billz.ai/v1";
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET;


const app = express();
app.use(cors());
app.use(express.json());


const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir);
}
const detailedFilePath = path.join(dataDir, 'detailed_debts.json');
const summaryFilePath = path.join(dataDir, 'summary_debts.json');


async function fetchAndProcessDebts() {
    try {
        console.log("Jarayon boshlandi: Billz API'dan ma'lumotlar olinmoqda...");
        const authResponse = await axios.post(`${API_BASE_URL}/auth/login`, { secret_token: SECRET_KEY });
        const accessToken = authResponse.data.data.access_token;
        console.log("✅ Avtorizatsiyadan muvaffaqiyatli o'tildi.");

        let allDebts = [];
        let page = 1;
        const limit = 500;

        while (true) {
            const response = await axios.get(`${API_BASE_URL}/debt`, {
                headers: { "Authorization": `Bearer ${accessToken}` },
                params: { page, limit, shop_ids: ALL_SHOPS, currency: "UZS", detalization_by_position: "true" }
            });
            const items = response.data.data || [];
            if (items.length === 0) break;
            allDebts.push(...items);
            console.log(`- ${page}-sahifa yuklandi. Jami yozuvlar: ${allDebts.length}`);
            page++;
        }
        console.log(`✅ Barcha ma'lumotlar yuklandi. Jami: ${allDebts.length} ta yozuv.`);

        const statusMap = {"unpaid": "To'lanmagan", "partial_paid": "Qisman to'langan", "paid": "To'langan", "fully_paid": "To'liq to'langan", "overdue": "To'lov muddati o'tgan"};
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const detailedDebts = allDebts.map(item => {
            const amount = Number(item.amount) || 0, paidAmount = Number(item.paid_amount) || 0, remainingAmount = amount - paidAmount;
            const createdAt = new Date(item.created_at), repaymentDate = item.repayment_date ? new Date(item.repayment_date) : null;
            let status = "", daysPassed = null;
            if (remainingAmount > 0) {
                daysPassed = Math.floor((today - createdAt) / (1000 * 3600 * 24));
                if (daysPassed < 30) status = "30 kundan kam"; else if (daysPassed < 60) status = "30-60 kun oralig'i"; else if (daysPassed < 90) status = "60-90 kun oralig'i"; else status = "O'ta muammoli mijozlar";
            } else { status = (repaymentDate && repaymentDate <= new Date(createdAt.setDate(createdAt.getDate() + 30))) ? "Vaqtida to'laganlar" : "To'langan vaqtida emas"; }
            return {"Qarz ID": item.id, "Kim yaratdi": item.created_by?.name, "Tranzaksiya ID": item.order_number, "Do‘kon": item.shop?.name, "Mijoz": item.customer?.name, "Mijoz ID": item.customer?.id, "Umumiy qarz summasi": amount, "To‘langan summa": paidAmount, "Qolgan qarz summasi": remainingAmount, "Telefon raqamlari": item.contact_phones?.join(", ") || "", "Holati": statusMap[item.status] || item.status, "Yaratilgan sana": item.created_at.substring(0, 10), "Qarz to‘lash sanasi": item.repayment_date?.substring(0, 10) || "", "Status": status, "O‘tgan kunlar": daysPassed };
        });
        console.log("✅ Ma'lumotlar qayta ishlandi (detailed).");

        const customerSummary = {};
        detailedDebts.forEach(debt => {
            const customerId = debt["Mijoz ID"];
            if (!customerId) return;
            if (!customerSummary[customerId]) customerSummary[customerId] = {"Mijoz ID": customerId, "Mijoz": debt["Mijoz"], "Umumiy qarz summasi": 0, "To‘langan summa": 0, "Qolgan qarz summasi": 0, "Telefon raqamlari": new Set(), "Kim yaratdi": debt["Kim yaratdi"]};
            const summary = customerSummary[customerId];
            summary["Umumiy qarz summasi"] += debt["Umumiy qarz summasi"]; summary["To‘langan summa"] += debt["To‘langan summa"]; summary["Qolgan qarz summasi"] += debt["Qolgan qarz summasi"];
            if(debt["Telefon raqamlari"]) summary["Telefon raqamlari"].add(debt["Telefon raqamlari"]);
        });

        let summaryDebts = Object.values(customerSummary).filter(c => c["Qolgan qarz summasi"] > 0).sort((a, b) => b["Qolgan qarz summasi"] - a["Qolgan qarz summasi"]);
        const allNotes = await db('notes').select('customer_id');
        const notesCountMap = allNotes.reduce((acc, note) => { acc[note.customer_id] = (acc[note.customer_id] || 0) + 1; return acc; }, {});
        summaryDebts.forEach(customer => {
            customer["Izohlar Soni"] = notesCountMap[customer["Mijoz ID"]] || 0;
            customer["Telefon raqamlari"] = Array.from(customer["Telefon raqamlari"]).join(', ');
        });
        console.log("✅ Ma'lumotlar umumlashtirildi (summary).");

        fs.writeFileSync(detailedFilePath, JSON.stringify(detailedDebts, null, 2));
        fs.writeFileSync(summaryFilePath, JSON.stringify(summaryDebts, null, 2));
        console.log(`✅ Natijalar 'data' papkasidagi JSON fayllarga muvaffaqiyatli saqlandi.`);
    } catch (error) {
        console.error("Xatolik yuz berdi:", error.response ? error.response.data : error.message);
    }
}


app.post('/api/login', async (req, res) => {
    try {
        const { name, phoneNumber } = req.body;
        const user = await db('users').where({ name }).first();
        if (!user || !await bcrypt.compare(phoneNumber, user.phone_number)) {
            return res.status(401).json({ message: "Ism yoki telefon raqami xato" });
        }
        const token = jwt.sign({ id: user.id, name: user.name }, JWT_SECRET, { expiresIn: '24h' });
        res.json({ token, userName: user.name });
    } catch (error) { res.status(500).json({ message: "Tizimda xatolik" }); }
});


const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    if (token == null) return res.sendStatus(401);
    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
};


app.get('/api/debts/detailed', authenticateToken, (req, res) => {
    try {
        const data = fs.readFileSync(detailedFilePath, 'utf-8'); res.json(JSON.parse(data));
    } catch (error) { res.status(500).json({ message: "Batafsil ma'lumotlarni o'qishda xatolik", error: error.message }); }
});

app.get('/api/debts/summary', authenticateToken, (req, res) => {
    try {
        const data = fs.readFileSync(summaryFilePath, 'utf-8'); res.json(JSON.parse(data));
    } catch (error) { res.status(500).json({ message: "Umumiy ma'lumotlarni o'qishda xatolik", error: error.message }); }
});

app.get('/api/notes/:customerId', authenticateToken, async (req, res) => {
    try {
        const { customerId } = req.params;
        const notes = await db('notes').where({ customer_id: customerId }).orderBy('created_at', 'desc');
        res.json(notes);
    } catch (error) { res.status(500).json({ message: "Izohlarni o'qishda xatolik", error: error.message }); }
});

// ...
app.post('/api/notes', authenticateToken, async (req, res) => {
    try {
        const { customer_id, note_text } = req.body;
        if (!customer_id || !note_text) {
            return res.status(400).json({ message: "Mijoz ID va izoh matni majburiy." });
        }


        const [newNoteId] = await db('notes').insert({
            customer_id: customer_id,
            note_text: note_text,
            author_name: req.user.name
        });

        const newNote = await db('notes').where({ id: newNoteId }).first();
        res.status(201).json(newNote);
    } catch (error) {

        console.error("Izoh saqlashda server xatoligi:", error);
        res.status(500).json({ message: "Izohni saqlashda xatolik", error: error.message });
    }
});


app.get('/api/users', authenticateToken, async (req, res) => {
    try {
        const users = await db('users').select('id', 'name'); // Parolni yubormaymiz!
        res.json(users);
    } catch (error) {
        res.status(500).json({ message: "Foydalanuvchilarni olishda xatolik" });
    }
});


app.post('/api/users', authenticateToken, async (req, res) => {
    try {
        const { name, phoneNumber } = req.body;
        if (!name || !phoneNumber) {
            return res.status(400).json({ message: "Ism va telefon raqami majburiy." });
        }

        const hashedPassword = await bcrypt.hash(phoneNumber, 10);
        const [newUserId] = await db('users').insert({
            name: name,
            phone_number: hashedPassword
        });

        const newUser = await db('users').select('id', 'name').where({ id: newUserId }).first();
        res.status(201).json(newUser);
    } catch (error) {

        if (error.code === 'SQLITE_CONSTRAINT') {
            return res.status(409).json({ message: "Bunday ismli foydalanuvchi allaqachon mavjud." });
        }
        res.status(500).json({ message: "Foydalanuvchi qo'shishda xatolik" });
    }
});


app.delete('/api/users/:id', authenticateToken, async (req, res) => {
    try {
        const { id } = req.params;
        const userToDelete = await db('users').where({ id }).select('name').first();


        if (!userToDelete) {
            return res.status(404).json({ message: "Foydalanuvchi topilmadi." });
        }

        // Asosiy ADMIN'ni tekshirish
        const adminName = process.env.ADMIN_NAME;
        if (userToDelete.name === adminName) {
            return res.status(403).json({ message: `Asosiy administrator "${adminName}"ni o'chirib bo'lmaydi.` });
        }

        const deletedCount = await db('users').where({ id }).del();

        // deletedCount tekshiruvi endi shart emas, chunki yuqorida tekshirdik
        res.status(200).json({ message: "Foydalanuvchi muvaffaqiyatli o'chirildi." });

    } catch (error) {
        res.status(500).json({ message: "Foydalanuvchi o'chirishda xatolik" });
    }
});



// ==========================================================
// 4. SERVERNI VA REJALASHTIRUVCHINI ISHGA TUSHIRISH
// ==========================================================

app.listen(PORT, () => {
    console.log(`🚀 Server http://localhost:${PORT} manzilida ishga tushdi.`);
});

cron.schedule('*/60 * * * *', () => {
    console.log('----------------------------------------------------');
    console.log('Rejalashtirilgan vazifa ishga tushdi (har 60 daqiqada)...');
    fetchAndProcessDebts();
});

console.log("Dastur ishga tushdi. Birinchi ma'lumotlar yangilanishi boshlanmoqda...");
fetchAndProcessDebts();
