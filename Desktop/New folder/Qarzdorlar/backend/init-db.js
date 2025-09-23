const db = require('./db');

async function setupDatabase() {
  try {
    // 1. "users" jadvali mavjudligini tekshirish
    const hasUsersTable = await db.schema.hasTable('users');
    if (!hasUsersTable) {
      console.log('"users" jadvali yaratilmoqda...');
      await db.schema.createTable('users', (table) => {
        table.increments('id').primary(); // Avtomatik o'suvchi ID
        table.string('name').notNullable(); // Foydalanuvchi ismi
        table.string('phone_number').notNullable().unique(); // Unikal telefon raqami (parol)
      });
      console.log('✅ "users" jadvali yaratildi.');
    } else {
      console.log('"users" jadvali allaqachon mavjud.');
    }

    // 2. "notes" jadvali mavjudligini tekshirish
    const hasNotesTable = await db.schema.hasTable('notes');
    if (!hasNotesTable) {
      console.log('Creating "notes" table...');
      await db.schema.createTable('notes', (table) => {
        table.increments('id').primary();
        table.string('customer_id').notNullable(); // Qaysi mijozga tegishli
        table.text('note_text').notNullable(); // Izoh matni
        table.string('author_name');
        // table.integer('author_id').references('id').inTable('users'); // Kim yozgani
        table.timestamp('created_at').defaultTo(db.fn.now()); // Yozilgan vaqti
      });
      console.log('✅ "notes" jadvali yaratildi.');
    } else {
      console.log('"notes" jadvali allaqachon mavjud.');
    }

  } catch (error) {
    console.error('Bazani sozlashda xatolik:', error);
  } finally {
    await db.destroy(); // Baza bilan aloqani uzish
  }
}

setupDatabase();
