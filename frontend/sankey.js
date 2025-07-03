// Interactive financial Sankey component using Plotly
// Expose as window.FinancialSankey
(function(){
    class FinancialSankey {
        constructor(container, data){
            this.container = (typeof container === 'string') ? document.getElementById(container) : container;
            this.data = Array.isArray(data) ? data.slice() : [];
            this.filtered = this.data;
            this._buildUI();
            this._bindEvents();
            this._applyFilter();
        }

        _buildUI(){
            this.container.classList.add('financial-sankey');
            // Controls
            const ctrl = document.createElement('div');
            ctrl.className = 'sankey-controls';
            ctrl.innerHTML = `
                <label>Mois <input type="month" id="sk-month"></label>
                <span>ou</span>
                <label>Du <input type="date" id="sk-start"></label>
                <label>au <input type="date" id="sk-end"></label>
                <button id="sk-apply">Filtrer</button>
                <button id="sk-export">Exporter</button>
            `;
            this.container.appendChild(ctrl);
            // Chart
            const chart = document.createElement('div');
            chart.id = 'sk-chart';
            chart.style.width = '100%';
            chart.style.height = '400px';
            this.container.appendChild(chart);
            // Remaining label
            const remain = document.createElement('div');
            remain.id = 'sk-remaining';
            this.container.appendChild(remain);
            // Details table
            const detail = document.createElement('div');
            detail.id = 'sk-detail';
            this.container.appendChild(detail);
            this.elements = {ctrl, chart, remain, detail,
                month: ctrl.querySelector('#sk-month'),
                start: ctrl.querySelector('#sk-start'),
                end: ctrl.querySelector('#sk-end'),
                apply: ctrl.querySelector('#sk-apply'),
                export: ctrl.querySelector('#sk-export')};
        }

        _bindEvents(){
            this.elements.apply.addEventListener('click', ()=> this._applyFilter());
            this.elements.export.addEventListener('click', ()=> this._export());
            window.addEventListener('resize', ()=> Plotly.Plots.resize(this.elements.chart));
        }

        _applyFilter(){
            const month = this.elements.month.value;
            let start = this.elements.start.value;
            let end = this.elements.end.value;
            if(month){
                const [y,m] = month.split('-');
                start = `${y}-${m}-01`;
                const lastDay = new Date(y, m, 0).toISOString().slice(0,10);
                end = lastDay;
                this.elements.start.value = start;
                this.elements.end.value = end;
            }
            this.filtered = this.data.filter(tx => {
                if(start && tx.date < start) return false;
                if(end && tx.date > end) return false;
                return true;
            });
            this._render();
        }

        _render(){
            const incomes = this.filtered.filter(t => t.montant > 0);
            const expenses = this.filtered.filter(t => t.montant < 0);
            const totalIncome = incomes.reduce((s,t)=>s+t.montant,0);
            const perCat = {};
            expenses.forEach(t => {
                perCat[t.categorie] = (perCat[t.categorie] || 0) + Math.abs(t.montant);
            });
            let totalExpense = Object.values(perCat).reduce((a,b)=>a+b,0);
            const major = [];
            let othersVal = 0;
            for(const [cat,val] of Object.entries(perCat)){
                if(totalExpense && val/totalExpense < 0.05){
                    othersVal += val;
                }else{
                    major.push({cat,val});
                }
            }
            if(othersVal>0) major.push({cat:'Autres', val:othersVal});
            major.sort((a,b)=>b.val-a.val);
            const remaining = totalIncome - totalExpense;

            const labels = ['Revenus', 'Total', ...major.map(c => c.cat)];
            if (remaining !== 0) labels.push('Solde');

            const source = [];
            const target = [];
            const values = [];
            const custom = [];

            // Revenus vers noeud "Total"
            source.push(0); target.push(1); values.push(totalExpense);
            custom.push({cat: 'Dépenses', pct: totalIncome ? totalExpense * 100 / totalIncome : 0});

            // Noeud "Total" vers categories
            major.forEach((c, i) => {
                source.push(1); target.push(i + 2); values.push(c.val);
                custom.push({cat: c.cat, pct: totalIncome ? c.val * 100 / totalIncome : 0});
            });

            // Flux vers solde restant
            if (remaining !== 0) {
                source.push(0); target.push(labels.length - 1); values.push(remaining);
                custom.push({cat: 'Solde', pct: totalIncome ? remaining * 100 / totalIncome : 0});
            }


            Plotly.react(this.elements.chart, [{
                type:'sankey',
                arrangement:'snap',
                node:{ label:labels, pad:15, thickness:20,
                    color: labels.map((_,i)=>{
                        if(i===0) return '#4caf50';
                        if(i===1) return '#9e9e9e';
                        if(remaining !== 0 && i===labels.length-1) return '#ff9800';
                        return '#2196f3';
                    }) },
                link:{
                    source, target, value: values,
                    customdata: custom,
                    hovertemplate: '%{customdata.cat}<br>€%{value:.2f} (%{customdata.pct:.1f}% du total)<extra></extra>'
                }
            }], {
                paper_bgcolor: getComputedStyle(document.documentElement).getPropertyValue('--bg-color').trim(),
                font:{color:getComputedStyle(document.documentElement).getPropertyValue('--text-color').trim()},
                margin:{t:20,l:20,r:20,b:20}
            }, {responsive:true});

            this.elements.chart.on('plotly_click', ev => {
                if(!ev.points.length) return;
                const idx = ev.points[0].pointIndex;
                // liens 1..major.length correspondent aux categories
                if(idx >= 1 && idx <= major.length){
                    const cat = major[idx-1].cat;
                    if(cat) this._showTransactions(cat);
                }
            });

            this.elements.remain.textContent = `Solde restant: €${remaining.toFixed(2)}`;
        }

        _showTransactions(cat){
            const list = this.filtered.filter(t => t.categorie === cat);
            if(!list.length){ this.elements.detail.textContent = 'Aucune transaction'; return; }
            const table = document.createElement('table');
            table.innerHTML = '<thead><tr><th>Date</th><th>Libellé</th><th>Montant</th></tr></thead>';
            const tbody = document.createElement('tbody');
            list.forEach(tx => {
                const tr = document.createElement('tr');
                const link = tx.id ? `<a href="${tx.id}" target="_blank">${tx.libelle || ''}</a>` : (tx.libelle || '');
                tr.innerHTML = `<td>${tx.date}</td><td>${link}</td><td class="amount">€${tx.montant.toFixed(2)}</td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            this.elements.detail.innerHTML = '';
            this.elements.detail.appendChild(table);
        }

        _export(){
            Plotly.toImage(this.elements.chart,{format:'png'}).then(url => {
                const a=document.createElement('a');
                a.href=url;
                a.download='sankey.png';
                a.click();
            });
        }
    }

    window.FinancialSankey = FinancialSankey;
})();
