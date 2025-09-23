const knex = require('knex')({
  client: 'sqlite3',
  connection: {
    filename: './qarzdorlar.sqlite'
  },
  useNullAsDefault: true
});

module.exports = knex;
