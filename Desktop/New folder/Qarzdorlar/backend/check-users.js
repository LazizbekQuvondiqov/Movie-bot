const db = require('./db');

async function checkUsers() {
    try {
        const users = await db.select('id', 'name').from('users');
        if (users.length > 0) {
            console.log("Bazadagi foydalanuvchilar:");
            console.table(users);
        } else {
            console.log("Bazadagi foydalanuvchilar ro'yxati bo'sh.");
        }
    } catch (error) {
        console.error("Xatolik:", error);
    } finally {
        db.destroy();
    }
}

checkUsers();
