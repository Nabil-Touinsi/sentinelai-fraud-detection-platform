import { Transaction, RiskScore, RiskLevel, Alert, AlertStatus, FullTransactionData, DashboardStats, PaymentMethod } from '../types';

// --- DATABASE MARCHANDS (REAL DATA MOCK) ---
const MERCHANTS_DB: Record<string, { names: string[], avg_basket: number, risky_hours?: boolean }> = {
  'Alimentation': {
    names: ['Carrefour City', 'Monoprix', 'Franprix', 'Auchan Supermarché', 'Leclerc Drive', 'Picard', 'Biocoop', 'Naturalia', 'Intermarché Express', 'Lidl'],
    avg_basket: 45
  },
  'Restaur. Rapide': {
    names: ['McDonald\'s', 'Burger King', 'KFC', 'Starbucks', 'Prêt à Manger', 'Subway', 'O\'Tacos', 'Domino\'s Pizza', 'Uber Eats', 'Deliveroo'],
    avg_basket: 25
  },
  'Restaurant': {
    names: ['Le Bouillon Chartier', 'Hippopotamus', 'Big Mamma', 'La Coupole', 'Café de Flore', 'Brasserie Lipp', 'Le Train Bleu', 'Vapiano', 'Bistro Régent'],
    avg_basket: 80
  },
  'Transport': {
    names: ['SNCF Connect', 'RATP', 'Uber', 'Bolt', 'G7 Taxi', 'Heetch', 'Lime', 'Dott', 'Air France', 'EasyJet'],
    avg_basket: 35
  },
  'Voyage': {
    names: ['Booking.com', 'Airbnb', 'Accor Hotels', 'Ibis Styles', 'Novotel', 'Expedia', 'Club Med', 'Hilton Paris'],
    avg_basket: 350
  },
  'E-commerce': {
    names: ['Amazon FR', 'Cdiscount', 'Fnac.com', 'Vinted', 'Leboncoin', 'Rakuten', 'AliExpress', 'Zalando', 'Asos', 'Showroomprivé'],
    avg_basket: 60
  },
  'Mode': {
    names: ['Zara', 'H&M', 'Uniqlo', 'Mango', 'Etam', 'Celio', 'Nike Store', 'Adidas', 'Printemps', 'Galeries Lafayette'],
    avg_basket: 70
  },
  'Luxe': {
    names: ['Louis Vuitton', 'Gucci', 'Hermès', 'Chanel', 'Cartier', 'Dior', 'Rolex', 'Saint Laurent', 'Tiffany & Co.', 'Balenciaga'],
    avg_basket: 1800
  },
  'High-Tech': {
    names: ['Apple Store', 'Boulanger', 'Darty', 'Fnac', 'LDLC', 'Micromania', 'Samsung Store', 'Grosbill'],
    avg_basket: 400
  },
  'Santé': {
    names: ['Pharmacie des Halles', 'Doctolib', 'CityPharma', 'Pharmacie Monge', 'Laboratoire Biogroup'],
    avg_basket: 40
  },
  'Carburant': {
    names: ['Total Energies', 'BP Station', 'Shell', 'Esso Express', 'Avia'],
    avg_basket: 60
  },
  'Abonnement': {
    names: ['Netflix', 'Spotify', 'Canal+', 'Adobe Creative Cloud', 'Microsoft 365', 'Basic-Fit', 'Fitness Park'],
    avg_basket: 20
  },
  'Divertissement': {
    names: ['UGC Ciné Cité', 'Gaumont Pathé', 'Ticketmaster', 'Olympia', 'DisneyLand Paris', 'Netflix'],
    avg_basket: 50
  }
};

const PAYMENT_METHODS: PaymentMethod[] = ['Carte Bancaire', 'Sans Contact', 'Apple Pay', 'En ligne'];

// --- In-Memory Database ---
let transactions: Transaction[] = [];
let riskScores: Record<string, RiskScore> = {};
let alerts: Alert[] = [];

// --- Helper Functions ---
const getRandomElement = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
const getRandomInt = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;

// --- ML Logic Simulation (Smart Scoring) ---
const calculateRisk = (t: Transaction): RiskScore => {
  let score = 0;
  const factors: string[] = [];
  const date = new Date(t.timestamp);
  const hour = date.getHours();

  // Reference stats (simulées)
  // On récupère le panier moyen théorique de la catégorie
  let categoryKey = Object.keys(MERCHANTS_DB).find(k => k === t.merchant_category) || 'Autre';
  const categoryData = MERCHANTS_DB[categoryKey] || { avg_basket: 50 };
  
  // 1. Analyse Montant vs Enseigne
  const ratio = t.amount / categoryData.avg_basket;
  
  if (t.merchant_category === 'Restaur. Rapide' && t.amount > 120) {
    score += 55;
    factors.push(`Montant aberrant pour ${t.merchant_name} (> 120€)`);
  } else if (ratio > 5) {
    score += 40;
    factors.push(`Montant 5x supérieur à la moyenne du secteur ${t.merchant_category}`);
  } else if (ratio > 3) {
    score += 20;
    factors.push(`Montant élevé pour cette enseigne`);
  }

  // 2. Analyse Horaire
  const isNight = hour >= 1 && hour <= 5;
  if (isNight) {
    if (['Luxe', 'High-Tech', 'Mode'].includes(t.merchant_category)) {
      score += 60;
      factors.push(`Achat ${t.merchant_category} en pleine nuit (${hour}h)`);
    } else if (t.merchant_category === 'Alimentation') {
      // Moins grave, peut être une épicerie de nuit
      score += 10;
    } else {
      score += 25;
      factors.push('Horaire atypique');
    }
  }

  // 3. Analyse Géographique (Zones Paris)
  // Simulation: Le 8ème, 1er, 16ème sont des zones "Riches" (Luxe ok), le 18, 19, 20 sont plus populaires
  const richZones = [1, 2, 8, 16, 7];
  
  if (t.merchant_category === 'Luxe' && !richZones.includes(t.zone_paris)) {
    // Achat Luxe hors quartiers chics -> légère suspicion ou bruit
    score += 15;
    factors.push(`Achat Luxe hors zones habituelles (Paris ${t.zone_paris})`);
  }

  // 4. Règles spécifiques Enseignes
  if (t.merchant_name.includes('Tabac') && t.amount > 300) {
    score += 45;
    factors.push('Montant élevé en bureau de tabac (Risque Cash/Prepaid)');
  }
  if (t.merchant_name === 'Apple Store' && t.amount > 2000 && t.payment_method === 'Sans Contact') {
     // Impossible de faire > 50 sans contact en théorie (sauf Apple Pay parfois), mais c'est un pattern fraude
     score += 30;
     factors.push('Montant élevé en Sans Contact');
  }

  // Noise / Aleatoire controlé
  score += Math.floor(Math.random() * 5);
  score = Math.min(100, score);

  let level = RiskLevel.LOW;
  if (score > 40) level = RiskLevel.MEDIUM;
  if (score > 70) level = RiskLevel.HIGH;

  return {
    transaction_id: t.id,
    score,
    level,
    factors,
    model_used: score > 50 ? 'XGBoost' : 'IsolationForest',
    analyzed_at: new Date().toISOString()
  };
};

// --- Service Methods ---

export const MockBackend = {
  
  // Générateur de transaction réaliste
  generateScenario: async (type: 'NORMAL' | 'FRAUD'): Promise<FullTransactionData> => {
      await new Promise(r => setTimeout(r, 600)); // Latence

      const now = new Date();
      let tx: Partial<Transaction> = {};

      if (type === 'NORMAL') {
        // Scénario Normal : Achat alimentaire ou transport jour
        const category = getRandomElement(['Alimentation', 'Transport', 'Restaur. Rapide', 'Abonnement']);
        const merchantData = MERCHANTS_DB[category];
        const name = getRandomElement(merchantData.names);
        
        // Montant autour de la moyenne (+/- 30%)
        const amount = merchantData.avg_basket * (0.7 + Math.random() * 0.6);
        
        tx = {
            amount: parseFloat(amount.toFixed(2)),
            merchant_category: category,
            merchant_name: name,
            timestamp: new Date(now.setHours(getRandomInt(8, 20))).toISOString(), // Journée
            zone_paris: getRandomInt(1, 20),
            payment_method: getRandomElement(['Carte Bancaire', 'Apple Pay', 'Sans Contact'])
        };

      } else {
        // Scénario Fraude : Luxe nuit, ou Tech montant énorme
        const scenarioType = getRandomInt(1, 3);
        
        if (scenarioType === 1) {
            // Luxe la nuit
            const merchantData = MERCHANTS_DB['Luxe'];
            tx = {
                merchant_category: 'Luxe',
                merchant_name: getRandomElement(merchantData.names),
                amount: parseFloat((merchantData.avg_basket * (0.8 + Math.random())).toFixed(2)),
                timestamp: new Date(now.setHours(getRandomInt(1, 4))).toISOString(), // Nuit profonde
                zone_paris: getRandomElement([10, 18, 19, 20]), // Quartiers moins typiques pour le luxe (cliché stat)
                payment_method: 'Carte Bancaire'
            };
        } else if (scenarioType === 2) {
            // Tech achat multiple ou gros montant
            const merchantData = MERCHANTS_DB['High-Tech'];
            tx = {
                merchant_category: 'High-Tech',
                merchant_name: getRandomElement(merchantData.names),
                amount: 2599.99, // Prix d'un MacBook Pro maxé
                timestamp: new Date(now.setHours(getRandomInt(10, 19))).toISOString(),
                zone_paris: getRandomInt(1, 20),
                payment_method: 'En ligne'
            };
        } else {
            // Resto rapide montant aberrant
            tx = {
                merchant_category: 'Restaur. Rapide',
                merchant_name: 'McDonald\'s',
                amount: 145.50,
                timestamp: new Date().toISOString(),
                zone_paris: 1,
                payment_method: 'Sans Contact'
            };
        }
      }

      // Finalize Object
      const fullTx: Transaction = {
          id: `TX-${Math.random().toString(36).substr(2, 6).toUpperCase()}`,
          card_holder_id: 'USER_123',
          amount: 0, 
          timestamp: new Date().toISOString(),
          zone_paris: 1,
          merchant_category: 'Autre',
          merchant_name: 'Inconnu',
          payment_method: 'Carte Bancaire',
          ...tx
      };

      // Ingest
      transactions.unshift(fullTx);
      const risk = calculateRisk(fullTx);
      riskScores[fullTx.id] = risk;

      let newAlert: Alert | undefined;
      if (risk.score > 60) {
        newAlert = {
            id: `DOSS-${Math.random().toString(36).substr(2, 6).toUpperCase()}`,
            transaction_id: fullTx.id,
            status: AlertStatus.NEW,
            created_at: new Date().toISOString(),
            risk_score_snapshot: risk.score
        };
        alerts.unshift(newAlert);
      }

      return { ...fullTx, risk, alert: newAlert };
  },

  // GET /transactions
  getTransactions: async (): Promise<FullTransactionData[]> => {
    // Si la liste est vide au démarrage, on génère 10 transactions fictives pour peupler
    if (transactions.length === 0) {
        for(let i=0; i<8; i++) await MockBackend.generateScenario('NORMAL');
        for(let i=0; i<2; i++) await MockBackend.generateScenario('FRAUD');
    }
    
    return transactions.map(t => ({
      ...t,
      risk: riskScores[t.id],
      alert: alerts.find(a => a.transaction_id === t.id)
    }));
  },

  // GET /alerts
  getAlerts: async (): Promise<(Alert & { transaction: Transaction, risk: RiskScore })[]> => {
    return alerts.map(a => {
      const t = transactions.find(tr => tr.id === a.transaction_id)!;
      return {
        ...a,
        transaction: t,
        risk: riskScores[t.id]
      };
    });
  },

  // PATCH /alerts/{id}
  updateAlertStatus: async (id: string, status: AlertStatus, comment?: string): Promise<void> => {
    const alert = alerts.find(a => a.id === id);
    if (alert) {
      alert.status = status;
      if (comment) alert.comment = comment;
    }
  },

  // Stats Dashboard
  getStats: async (): Promise<DashboardStats> => {
    const totalTransactionsToday = transactions.length;
    const openAlerts = alerts.filter(a => a.status !== AlertStatus.CLOSED).length;
    const criticalAlerts = alerts.filter(a => a.status === AlertStatus.NEW && a.risk_score_snapshot > 80).length;
    
    return {
      totalTransactionsToday,
      openAlerts,
      criticalAlerts,
      avgResolutionTimeMinutes: 24
    };
  }
};