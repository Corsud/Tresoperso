function TransactionTable() {
  const [transactions, setTransactions] = React.useState([]);
  const [filters, setFilters] = React.useState({
    category: '',
    startDate: '',
    endDate: '',
    minAmount: '',
    maxAmount: ''
  });
  const [sortBy, setSortBy] = React.useState('date');
  const [order, setOrder] = React.useState('desc');

  const fetchData = React.useCallback(() => {
    const params = new URLSearchParams();
    if (filters.category) params.append('category', filters.category);
    if (filters.startDate) params.append('start_date', filters.startDate);
    if (filters.endDate) params.append('end_date', filters.endDate);
    if (filters.minAmount) params.append('min_amount', filters.minAmount);
    if (filters.maxAmount) params.append('max_amount', filters.maxAmount);
    params.append('sort_by', sortBy);
    params.append('order', order);
    fetch('/transactions?' + params.toString())
      .then(r => r.json())
      .then(setTransactions);
  }, [filters, sortBy, order]);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div>
      <h2>Transactions</h2>
      <div>
        <input name="category" placeholder="Catégorie" value={filters.category} onChange={handleFilterChange} />
        <input type="date" name="startDate" value={filters.startDate} onChange={handleFilterChange} />
        <input type="date" name="endDate" value={filters.endDate} onChange={handleFilterChange} />
        <input type="number" step="0.01" name="minAmount" placeholder="Montant min" value={filters.minAmount} onChange={handleFilterChange} />
        <input type="number" step="0.01" name="maxAmount" placeholder="Montant max" value={filters.maxAmount} onChange={handleFilterChange} />
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
          <option value="date">Date</option>
          <option value="amount">Montant</option>
        </select>
        <select value={order} onChange={e => setOrder(e.target.value)}>
          <option value="desc">Descendant</option>
          <option value="asc">Ascendant</option>
        </select>
        <button onClick={fetchData}>Filtrer</button>
      </div>
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Moyen de paiement</th>
            <th>Libellé</th>
            <th>Montant</th>
            <th>Catégorie</th>
            <th>Pointée</th>
            <th>A analyser</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map(t => (
            <tr key={t.id}>
              <td>{t.date}</td>
              <td>{t.type}</td>
              <td>{t.payment_method}</td>
              <td>{t.label}</td>
              <td>{t.amount}</td>
              <td>{t.category || ''}</td>
              <td><input type="checkbox" checked={t.reconciled} onChange={e => {
                fetch('/transactions/' + t.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reconciled: e.target.checked})})
                  .then(fetchData);
              }} /></td>
              <td><input type="checkbox" checked={t.to_analyze} onChange={e => {
                fetch('/transactions/' + t.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({to_analyze: e.target.checked})})
                  .then(fetchData);
              }} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoginForm({ onLogin }) {
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(() => onLogin())
      .catch(() => setError('Identifiants invalides'));
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Utilisateur" />
      </div>
      <div>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Mot de passe" />
      </div>
      {error && <div style={{color: 'red'}}>{error}</div>}
      <button type="submit">Connexion</button>
    </form>
  );
}

function App() {
  const [loggedIn, setLoggedIn] = React.useState(false);

  React.useEffect(() => {
    fetch('/me')
      .then(r => r.ok && r.json())
      .then(data => {
        if (data && data.username) setLoggedIn(true);
      });
  }, []);

  if (!loggedIn) {
    return <LoginForm onLogin={() => setLoggedIn(true)} />;
  }
  return <TransactionTable />;
}

ReactDOM.render(<App />, document.getElementById('root'));
