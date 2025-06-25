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
            <th>Libellé</th>
            <th>Montant</th>
            <th>Catégorie</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map(t => (
            <tr key={t.id}>
              <td>{t.date}</td>
              <td>{t.label}</td>
              <td>{t.amount}</td>
              <td>{t.category || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

ReactDOM.render(<TransactionTable />, document.getElementById('root'));
