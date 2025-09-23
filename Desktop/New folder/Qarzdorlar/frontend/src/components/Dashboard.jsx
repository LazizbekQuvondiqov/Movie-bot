import { useState, useEffect } from 'react';
import axios from 'axios';


const getStatusClass = (statusText) => {
  if (!statusText) return '';
  return 'status-' + statusText
    .toLowerCase()
    .replace(/ /g, '-') // bo'shliqlarni chiziqchaga
    .replace(/[^a-z0-9-]/g, ''); // faqat harf, raqam va chiziqchani qoldirish
};

export default function Dashboard({ handleLogout }) {


  // Asosiy ma'lumotlar uchun state'lar
  const [summaryData, setSummaryData] = useState([]);
  const [detailedData, setDetailedData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('Barchasi'); // <-- YANGI STATE
  const [sortConfig, setSortConfig] = useState({ key: 'Qolgan qarz summasi', direction: 'desc' }); // standart holatda qolgan qarz bo'yicha kamayish


  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [activeTab, setActiveTab] = useState('debts');
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [isNotesLoading, setIsNotesLoading] = useState(false);

  // Foydalanuvchilarni boshqarish uchun yangi state'lar
  const [isUsersModalOpen, setIsUsersModalOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const [newUserName, setNewUserName] = useState('');
  const [newUserPhone, setNewUserPhone] = useState('');
  const [userError, setUserError] = useState('');



  // Komponent ilk marta ishga tushganda barcha kerakli ma'lumotlarni yuklash
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summaryRes, detailedRes] = await Promise.all([
          axios.get('http://localhost:3001/api/debts/summary'),
          axios.get('http://localhost:3001/api/debts/detailed')
        ]);
        setSummaryData(summaryRes.data);
        setDetailedData(detailedRes.data);
      } catch (error) {
        console.error("Ma'lumotlarni yuklashda xatolik:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // KPI ko'rsatkichlarini hisoblash
  const kpiData = {
    totalRemainingDebt: summaryData.reduce((acc, customer) => acc + customer['Qolgan qarz summasi'], 0),
    totalPaidAmount: summaryData.reduce((acc, customer) => acc + customer['To‘langan summa'], 0),
    activeDebtorsCount: summaryData.length
  };



  // Saralashni boshqarish uchun funksiya
  const requestSort = (key) => {
    let direction = 'asc'; // o'sish
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc'; // kamayish
    }
    setSortConfig({ key, direction });
  };


// ...
  // Qidiruv, filter va saralashni bir joyda bajarish
  const sortedAndFilteredData = () => {
    let filterableData = [...summaryData];

    // 1. Status bo'yicha filtrlash
    if (selectedStatus !== 'Barchasi') {
      const filteredCustomerIds = new Set(
        detailedData
          .filter(debt => debt['Status'] === selectedStatus)
          .map(debt => debt['Mijoz ID'])
      );
      filterableData = filterableData.filter(customer => filteredCustomerIds.has(customer['Mijoz ID']));
    }

    // 2. Qidiruv bo'yicha filtrlash
    if (searchTerm) {
      filterableData = filterableData.filter(customer =>
        customer['Mijoz']?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        customer['Telefon raqamlari']?.includes(searchTerm)
      );
    }

    // 3. Saralash
    if (sortConfig.key !== null) {
      filterableData.sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }

    return filterableData;
  };

  const filteredData = sortedAndFilteredData(); // Funksiyani chaqirib, natijani olamiz
// ...


  // Modal oynani ochish funksiyasi
  const handleRowClick = async (customer, defaultTab = 'debts') => {
    setSelectedCustomer(customer);
    setActiveTab(defaultTab);

    setIsNotesLoading(true);
    try {
        const res = await axios.get(`http://localhost:3001/api/notes/${customer['Mijoz ID']}`);
        setNotes(res.data);
    } catch (error) {
        console.error("Izohlarni yuklashda xato:", error);
    } finally {
        setIsNotesLoading(false);
    }
  };

  // Modal oynani yopish funksiyasi
  const closeModal = () => {
    setSelectedCustomer(null);
    setNotes([]);
    setNewNote('');
  };

  // Yangi izoh qo'shish funksiyasi
  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!newNote.trim()) return;

    try {
        const response = await axios.post('http://localhost:3001/api/notes', {
            customer_id: selectedCustomer['Mijoz ID'],
            note_text: newNote
        });

        // Frontenddagi ma'lumotni ham yangilaymiz
        // 1. Yangi izohni ro'yxatga qo'shamiz
        setNotes([response.data, ...notes]);
        // 2. Asosiy jadvaldagi izohlar sonini bittaga oshiramiz
        setSummaryData(summaryData.map(cust =>
            cust['Mijoz ID'] === selectedCustomer['Mijoz ID']
                ? { ...cust, 'Izohlar Soni': (cust['Izohlar Soni'] || 0) + 1 }
                : cust
        ));

        setNewNote('');
    } catch (error) {
        console.error("Izoh saqlashda xato:", error);
        alert("Izohni saqlab bo'lmadi!");
    }
  };

  // Tanlangan mijozning batafsil qarz ma'lumotlarini filtrlash
  const customerDetailedDebts = selectedCustomer
    ? detailedData.filter(debt => debt['Mijoz ID'] === selectedCustomer['Mijoz ID'])
    : [];
  // ... (masalan, customerDetailedDebts hisoblanib bo'lganidan keyin)

  // Foydalanuvchilar modalini ochish
  const openUsersModal = async () => {
    setUserError(''); // Xatolikni tozalash
    try {
        const response = await axios.get('http://localhost:3001/api/users');
        setUsers(response.data);
        setIsUsersModalOpen(true);
    } catch (error) {
        console.error("Foydalanuvchilarni olishda xatolik:", error);
        setUserError("Foydalanuvchilarni yuklab bo'lmadi.");
    }
  };

  // Yangi foydalanuvchi qo'shish
  const handleAddUser = async (e) => {
    e.preventDefault();
    setUserError('');
    try {
        const response = await axios.post('http://localhost:3001/api/users', {
            name: newUserName,
            phoneNumber: newUserPhone
        });
        setUsers([...users, response.data]);
        setNewUserName('');
        setNewUserPhone('');
    } catch (error) {
        setUserError(error.response?.data?.message || "Xatolik yuz berdi");
    }
  };

  // Foydalanuvchini o'chirish
  const handleDeleteUser = async (userId) => {
    if (window.confirm("Haqiqatan ham bu foydalanuvchini o'chirmoqchimisiz?")) {
        try {
            await axios.delete(`http://localhost:3001/api/users/${userId}`);
            setUsers(users.filter(user => user.id !== userId));
        } catch (error) {
            alert(error.response?.data?.message || "O'chirishda xatolik!");
        }
    }
  };


  return (

      <div className="container">
        <div className="dashboard-header">
            <h1>Qarzdorlar Paneli</h1>
            {/* O'zgartirish shu yerda */}
            <div className="header-buttons">
                <button onClick={openUsersModal} className="manage-users-btn">Foydalanuvchilarni Boshqarish</button>
                <button onClick={handleLogout} className="logout-btn">Chiqish</button>
            </div>
        </div>


      <div className="kpi-cards">
        <div className="kpi-card"><h3>Faol Qarzdorlar</h3><p>{kpiData.activeDebtorsCount.toLocaleString()}</p></div>
        <div className="kpi-card remaining-debt-card"><h3>Umumiy Qolgan Qarz</h3><p>{kpiData.totalRemainingDebt.toLocaleString()} so'm</p></div>
        <div className="kpi-card paid-amount-card"><h3>Jami To'langan</h3><p>{kpiData.totalPaidAmount.toLocaleString()} so'm</p></div>
      </div>

      <hr />


      <div className="controls-container">
        <h2>Mijozlar bo'yicha umumiy holat</h2>
        <div className="filters"> {/* Qidiruv va filtrni bitta joyga yig'amiz */}

          {/* Status filteri */}

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="status-filter"
          >
            <option value="Barchasi">Barcha statuslar</option>
            <optgroup label="To'lanmaganlar">
              <option value="30 kundan kam">30 kundan kam</option>
              <option value="30-60 kun oralig'i">30-60 kun oralig'i</option>
              <option value="60-90 kun oralig'i">60-90 kun oralig'i</option>
              <option value="O'ta muammoli mijozlar">O'ta muammoli mijozlar</option>
            </optgroup>
            <optgroup label="To'langanlar">
              <option value="Vaqtida to'laganlar">Vaqtida to'laganlar</option>
              <option value="To'langan vaqtida emas">To'langan vaqtida emas</option>
            </optgroup>
          </select>


          {/* Qidiruv maydoni */}
          <div className="search-container">
            <input
              type="text"
              placeholder="Mijoz ismi yoki raqami..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>


      {loading ? ( <p>Ma'lumotlar yuklanmoqda...</p> ) : (


        <div className="table-container">
          <table>
            <thead>
              <tr>
                {/* 1. Sarlavhani qayta qo'shamiz */}
                <th onClick={() => requestSort('Mijoz ID')}>
                  Mijoz ID {sortConfig.key === 'Mijoz ID' ? (sortConfig.direction === 'asc' ? '▲' : '▼') : null}
                </th>
                <th onClick={() => requestSort('Mijoz')}>
                  Mijoz {sortConfig.key === 'Mijoz' ? (sortConfig.direction === 'asc' ? '▲' : '▼') : null}
                </th>
                <th onClick={() => requestSort('Telefon raqamlari')}>
                  Telefon raqamlari
                </th>
                <th onClick={() => requestSort('Umumiy qarz summasi')}>
                  Umumiy Qarz {sortConfig.key === 'Umumiy qarz summasi' ? (sortConfig.direction === 'asc' ? '▲' : '▼') : null}
                </th>
                <th onClick={() => requestSort('To‘langan summa')}>
                  To'langan
                </th>
                <th onClick={() => requestSort('Qolgan qarz summasi')}>
                  Qolgan Qarz {sortConfig.key === 'Qolgan qarz summasi' ? (sortConfig.direction === 'asc' ? '▲' : '▼') : null}
                </th>
                <th>Izohlar</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((customer) => (
                <tr key={customer['Mijoz ID']} onClick={() => handleRowClick(customer, 'debts')}>
                  {/* 2. Har bir qatordagi ID'ni qayta qo'shamiz */}
                  <td>{customer['Mijoz ID']}</td>
                  <td>{customer['Mijoz']}</td>
                  <td>{customer['Telefon raqamlari']}</td>
                  <td>{customer['Umumiy qarz summasi'].toLocaleString()}</td>
                  <td>{customer['To‘langan summa'].toLocaleString()}</td>
                  <td className="remaining-debt">{customer['Qolgan qarz summasi'].toLocaleString()}</td>
                  <td>
                    <button
                      className={`notes-btn ${customer['Izohlar Soni'] > 0 ? 'has-notes' : ''}`}
                      onClick={(e) => { e.stopPropagation(); handleRowClick(customer, 'notes'); }}
                    >
                      {customer['Izohlar Soni'] > 0 ? `${customer['Izohlar Soni']} ta izoh` : 'Qo\'shish'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      )}

      {/* MODAL OYNA */}
      {selectedCustomer && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close-btn" onClick={closeModal}>&times;</button>
            <h2>{selectedCustomer['Mijoz']}</h2>

            <div className="modal-tabs">
                <button className={`tab-btn ${activeTab === 'debts' ? 'active' : ''}`} onClick={() => setActiveTab('debts')}>Qarzlar Ro'yxati</button>
                <button className={`tab-btn ${activeTab === 'notes' ? 'active' : ''}`} onClick={() => setActiveTab('notes')}>Izohlar</button>
            </div>

            <div className="modal-tab-content">
                {activeTab === 'debts' && (
                  customerDetailedDebts.length > 0 ? (
                    <div className="table-container">
                      <table>
                        <thead>
                          <tr><th>Umumiy summa</th><th>To'langan</th><th>Qolgan</th><th>Holati</th><th>Yaratilgan sana</th><th>Status</th><th>O'tgan kunlar</th></tr>
                        </thead>

                          <tbody>
                            {customerDetailedDebts.map(debt => (
                              <tr key={debt['Qarz ID']}>
                                <td>{debt['Umumiy qarz summasi'].toLocaleString()}</td>
                                <td>{debt['To‘langan summa'].toLocaleString()}</td>
                                <td className="remaining-debt">{debt['Qolgan qarz summasi'].toLocaleString()}</td>
                                <td>{debt['Holati']}</td>
                                <td>{debt['Yaratilgan sana']}</td>
                                <td>
                                  <span className={`status-badge ${getStatusClass(debt['Status'])}`}>
                                    {debt['Status']}
                                  </span>
                                </td>
                                <td>{debt['O‘tgan kunlar'] !== null ? `${debt['O‘tgan kunlar']} kun` : '-'}</td>
                              </tr>
                            ))}
                          </tbody>

                      </table>
                    </div>
                  ) : (<p>Bu mijoz uchun batafsil qarz ma'lumotlari topilmadi.</p>)
                )}

                {activeTab === 'notes' && (
                    <div className="notes-section">
                        <form onSubmit={handleAddNote} className="note-form">
                            <textarea value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="Yangi izoh yozing..." rows="3"></textarea>
                            <button type="submit">Saqlash</button>
                        </form>

                        <div className="notes-list">
                            {isNotesLoading ? <p>Izohlar yuklanmoqda...</p> : (
                                notes.length > 0 ? notes.map(note => (
                                    <div key={note.id} className="note-item">
                                        <p>{note.note_text}</p>
                                        {/* Muallif va sana uchun yangi qator */}
                                        <div className="note-meta">
                                            <span className="note-author">{note.author_name || 'Noma\'lum'}</span>
                                            <span className="note-date">{new Date(note.created_at).toLocaleString()}</span>
                                        </div>
                                    </div>
                                )) : <p>Bu mijoz uchun hali izohlar mavjud emas.</p>
                            )}
                        </div>

                    </div>
                )}
            </div>
          </div>
        </div>
      )}


  {/* ========================================================== */}
  {/* FOYDALANUVCHILARNI BOSHQARISH UCHUN YANGI MODAL OYNA */}
  {/* ========================================================== */}
  {isUsersModalOpen && (
    <div className="modal-overlay" onClick={() => setIsUsersModalOpen(false)}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={() => setIsUsersModalOpen(false)}>&times;</button>
        <h2>Foydalanuvchilarni Boshqarish</h2>

        <form onSubmit={handleAddUser} className="user-form">
          <h3>Yangi foydalanuvchi qo'shish</h3>
          <div className="form-row">
            <input type="text" placeholder="Ism" value={newUserName} onChange={(e) => setNewUserName(e.target.value)} required />
            <input type="text" placeholder="Telefon raqami (parol)" value={newUserPhone} onChange={(e) => setNewUserPhone(e.target.value)} required />
            <button type="submit">Qo'shish</button>
          </div>
          {userError && <p className="error-message">{userError}</p>}
        </form>

        <hr/>

        <h3>Mavjud foydalanuvchilar</h3>
        <ul className="users-list">
          {users.map(user => (
            <li key={user.id}>
              <span>{user.name}</span>
              <button onClick={() => handleDeleteUser(user.id)} className="delete-user-btn">O'chirish</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )}

</div> // Bu .container'ning yopilishi
  );
}

