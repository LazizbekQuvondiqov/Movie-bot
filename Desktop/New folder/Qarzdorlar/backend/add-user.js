const db = require('./db');
const bcrypt = require('bcryptjs');

const name = process.argv[2];
const phoneNumber = process.argv[3];

if (!name || !phoneNumber) {
    console.error("Iltimos, ism va telefon raqamini kiriting. Namuna: node add-user.js Ali 998901234567");
    process.exit(1);
}

async function addUser() {
    try {
        const hashedPassword = await bcrypt.hash(phoneNumber, 10); // Parolni (tel. raqamni) heshlaymiz
        await db('users').insert({
            name: name,
            phone_number: hashedPassword
        });
        console.log(`✅ Foydalanuvchi "${name}" muvaffaqiyatli qo'shildi!`);
    } catch (error) {
        console.error("Foydalanuvchi qo'shishda xatolik:", error.message);
    } finally {
        db.destroy();
    }
}

addUser();
