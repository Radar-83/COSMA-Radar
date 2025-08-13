import React, { useEffect, useState, useCallback, useRef } from 'react';
import './App.css';
import logo from './logo_cosma.png';
import menuIcon from './menu.png';
import Select from 'react-select';
import { loadData, status, runJob, stopJob } from "./api";


function App() {
  // États pour les données et les filtres
  const [profiles, setProfiles] = useState([]);
  const [data, setData] = useState([]);
  const [expandedIndex, setExpandedIndex] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedCountries, setSelectedCountries] = useState([]);
  const [filterAppliedCountries, setFilterAppliedCountries] = useState([]);
  const [countries, setCountries] = useState([]);
  const [selectedTheme, setSelectedTheme] = useState("ALL");

  const [selectedPhase, setSelectedPhase] = useState("ALL");
  const [phases, setPhases] = useState(["ALL"]);
  const [showingFavoritesOnly, setShowingFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState([]);
  const [openPanel, setOpenPanel] = useState(null);
  const [showActionIndex, setShowActionIndex] = useState(null);
  const [showReasoningIndex, setShowReasoningIndex] = useState(null);
  const [showIdealContactIndex, setShowIdealContactIndex] = useState(null);

  // États pour le pipeline
  const [running, setRunning] = useState(false);
  const [lastRunLog, setLastRunLog] = useState("");
  const [jobStatus, setJobStatus] = useState({
    running: false,
    started_at: null,
    ended_at: null,
    returncode: null,
    duration_sec: null,
    executable: null,
    cwd: null,
    pid: null,
  });

  // États pour les métadonnées
  const [dataMeta, setDataMeta] = useState(null);

  // États pour les mots-clés
  const [keywords, setKeywords] = useState([]);
  const [kwInput, setKwInput] = useState("");
  const [kwBusy, setKwBusy] = useState(false);
  const [kwError, setKwError] = useState("");

  // États pour le menu
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Thèmes disponibles
  const themes = ["ALL", "OFFSHORE WIND FARMS", "SUBMARINE CABLES", "PIPELINES", "MARINE INFRASTRUCTURE", "OTHER"];

  // Gestion du menu
  useEffect(() => {
    const onClickAway = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onEsc = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onClickAway);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onClickAway);
      document.removeEventListener('keydown', onEsc);
    };
  }, []);

  // Load the JSON at startup using API function
  useEffect(() => {
    loadData()
      .then(data => {
        setData(data);
        const cleaned = (Array.isArray(data) ? data : []).filter(
          (profile) => profile.company_name && profile.score_global
        );
        const uniqueCountries = Array.from(
          new Set(
            cleaned
              .map((p) => {
                const loc = p.location || "";
                const parts = loc.split(',').map((s) => s.trim());
                return parts[parts.length - 1];
              })
              .filter((c) => c && c !== "Erreur" && c !== "Non trouvée")
          )
        ).sort();

        setCountries(uniqueCountries);

        const uniquePhases = Array.from(new Set(
          cleaned.flatMap(p => String(p.project_phase || '')
            .split(/[\/;,]+/)
            .map(s => s.trim())
            .filter(Boolean)
          )
        )).sort();
        setPhases(["ALL", ...uniquePhases]);
        setProfiles(cleaned.sort((a, b) => (b.score_global || 0) - (a.score_global || 0)));
      })
      .catch(e => alert("Impossible de charger les données. Assure-toi que le backend tourne. " + e));
  }, []);

  // Poll status to mirror localhost behavior
  useEffect(() => {
    const id = setInterval(() => status().then(setJobStatus).catch(() => {}), 2000);
    return () => clearInterval(id);
  }, []);

  // Chargement des données (fonction de backup si besoin)
  const reloadData = useCallback(async () => {
    try {
      const res = await fetch('/api/data');
      if (!res.ok) throw new Error(`Erreur API /api/data: ${res.status} ${res.statusText}`);
      const data = await res.json();
      const cleaned = (Array.isArray(data) ? data : []).filter(
        (profile) => profile.company_name && profile.score_global
      );
      const uniqueCountries = Array.from(
        new Set(
          cleaned
            .map((p) => {
              const loc = p.location || "";
              const parts = loc.split(',').map((s) => s.trim());
              return parts[parts.length - 1];
            })
            .filter((c) => c && c !== "Erreur" && c !== "Non trouvée")
        )
      ).sort();

      setCountries(uniqueCountries);

      const uniquePhases = Array.from(new Set(
        cleaned.flatMap(p => String(p.project_phase || '')
          .split(/[\/;,]+/)
          .map(s => s.trim())
          .filter(Boolean)
        )
      )).sort();
      setPhases(["ALL", ...uniquePhases]);
      setProfiles(cleaned.sort((a, b) => (b.score_global || 0) - (a.score_global || 0)));
    } catch (e) {
      console.error("Erreur de chargement JSON :", e);
      alert("Impossible de charger les données (voir console). Assurez-vous que le backend est démarré.");
    }
  }, []);

  const fetchDataMeta = useCallback(async () => {
    try {
      const r = await fetch('/api/data/meta');
      if (r.ok) setDataMeta(await r.json());
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchDataMeta();
  }, [fetchDataMeta]);

  // Exécution du pipeline using API function
  const runPipeline = async () => {
    setRunning(true);
    setLastRunLog("");
    try {
      const res = await runJob();
      console.log(res);
      setLastRunLog(`06_Executable lancé avec PID: ${res.pid}`);
      await reloadData();
      await fetchDataMeta();
    } catch (e) {
      alert(e.message);
      setLastRunLog(String(e));
    } finally {
      setRunning(false);
    }
  };

  // Arrêter le pipeline using API function
  const stopPipeline = async () => {
    try {
      const res = await stopJob();
      console.log(res);
      if (res.stopped) {
        setLastRunLog(`Process arrêté (PID: ${res.pid})`);
      } else {
        setLastRunLog(`Arrêt échoué: ${res.reason}`);
      }
      setRunning(false);
    } catch (e) {
      alert(e.message);
      console.error("Erreur lors de l'arrêt:", e);
      setLastRunLog(`Erreur lors de l'arrêt: ${e}`);
    }
  };

  // Gestion des favoris et de l'expansion des profils
  const toggleExpand = (index) => {
    setExpandedIndex(expandedIndex === index ? null : index);
    setShowActionIndex(null);
    setShowReasoningIndex(null);
    setShowIdealContactIndex(null);
  };

  const toggleFavorite = (postId) => {
    setFavorites((prev) =>
      prev.includes(postId) ? prev.filter((id) => id !== postId) : [...prev, postId]
    );
  };

  const filteredProfiles = profiles.filter((profile) => {
    const matchesSearch = profile.company_name.toLowerCase().includes(search.toLowerCase());
    const loc = profile.location || "";
    const country = loc.split(',').pop().trim();
    const matchesCountry =
      filterAppliedCountries.length === 0 || filterAppliedCountries.includes(country);
    const theme = profile.theme?.toUpperCase() || "OTHER";
    
    let matchesTheme = false;
    if (selectedTheme === "ALL") {
      matchesTheme = true;
    } else if (selectedTheme === "OTHER") {
      // Inclure les thèmes qui sont vides/manquants OU qui contiennent "other"
      matchesTheme = !profile.theme || 
                   profile.theme.toLowerCase().includes('other') ||
                   !["OFFSHORE WIND FARMS", "SUBMARINE CABLES", "PIPELINES", "MARINE INFRASTRUCTURE"].some(t => 
                     theme.split(",").map(th => th.trim()).includes(t)
                   );
    } else {
      matchesTheme = theme.split(",").map(t => t.trim()).includes(selectedTheme);
    }
    
    const matchesFavorites = !showingFavoritesOnly || favorites.includes(profile.post_id);

    const projectPhaseRaw = (profile.project_phase || "");
    const phaseTokens = projectPhaseRaw.split(/[\/;,]+/).map(s => s.trim().toLowerCase()).filter(Boolean);
    const matchesPhase = selectedPhase === "ALL" || phaseTokens.includes(String(selectedPhase).toLowerCase());

    return matchesSearch && matchesCountry && matchesTheme && matchesPhase && matchesFavorites;
  });

  // Gestion des filtres pays
  const handleCountryChange = (selectedOptions) => {
    setSelectedCountries(selectedOptions || []);
  };

  const applyCountryFilter = () => {
    const selectedValues = selectedCountries.map((option) => option.value);
    setFilterAppliedCountries(selectedValues);
    setOpenPanel(null);
  };

  const resetCountryFilter = () => {
    setSelectedCountries([]);
    setFilterAppliedCountries([]);
    setOpenPanel(null);
  };

  // Gestion des mots-clés
  const loadKeywords = async () => {
    try {
      const res = await fetch('/api/keywords');
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      setKeywords(body.keywords || []);
      setKwError("");
    } catch (e) {
      setKwError(String(e));
    }
  };

  const addKeyword = async () => {
    const value = (kwInput || "").trim();
    if (!value) return;
    setKwBusy(true);
    try {
      const res = await fetch('/api/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: value }),
      });
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      setKeywords(body.keywords || []);
      setKwInput("");
      setKwError("");
    } catch (e) {
      setKwError(String(e));
    } finally {
      setKwBusy(false);
    }
  };

  const removeKeyword = async (kw) => {
    setKwBusy(true);
    try {
      const res = await fetch('/api/keywords', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: kw }),
      });
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      setKeywords(body.keywords || []);
      setKwError("");
    } catch (e) {
      setKwError(String(e));
    } finally {
      setKwBusy(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-top">
          <div
            className="logo-container"
            onClick={() => {
              setSelectedCountries([]);
              setFilterAppliedCountries([]);
              setSelectedTheme("ALL");
              setSelectedPhase("ALL");
              setSearch("");
              setShowingFavoritesOnly(false);
              setOpenPanel(null);
            }}
          >
            <img src={logo} alt="Cosma Logo" className="logo clickable" />
            <span className="logo-text">Radar</span>
          </div>
          <div className="menu-wrapper" ref={menuRef}>
            <button
              className={`menu-button ${menuOpen ? 'open' : ''}`}
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-controls="header-menu-dropdown"
              aria-label="Ouvrir le menu"
              onClick={() => setMenuOpen(v => !v)}
            >
              <img src={menuIcon} alt="" />
            </button>
            <div
              id="header-menu-dropdown"
              className={`menu-dropdown ${menuOpen ? 'visible' : 'hidden'}`}
              role="menu"
            >
              <button
                className="menu-item"
                role="menuitem"
                onClick={async () => {
                  await loadKeywords();
                  setOpenPanel('keywords');
                  setMenuOpen(false);
                }}
              >
                Mots-clés
              </button>
              <button
                className="menu-item"
                role="menuitem"
                onClick={() => {
                  reloadData();
                  setMenuOpen(false);
                }}
              >
                Recharger les données
              </button>
            </div>
          </div>
        </div>
        <div className="header-buttons">
          <div className="left-controls">
            <div style={{ position: 'relative' }}>
              <button
                className={`toggle-button ${openPanel === 'country' ? 'active' : ''}`}
                onClick={() => setOpenPanel(openPanel === 'country' ? null : 'country')}
              >
                Pays
              </button>
              {openPanel === 'country' && (
                <div className="dropdown-panel theme-selector">
                  <Select
                    options={countries.map((c) => ({ value: c, label: c }))}
                    isMulti
                    value={selectedCountries}
                    onChange={handleCountryChange}
                    className="select-wrapper"
                    classNamePrefix="react-select"
                  />
                  <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                    <button onClick={applyCountryFilter}>Rechercher</button>
                    <button onClick={resetCountryFilter}>Réinitialiser</button>
                  </div>
                </div>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <button
                className={`toggle-button ${openPanel === 'theme' ? 'active' : ''}`}
                onClick={() => setOpenPanel(openPanel === 'theme' ? null : 'theme')}
              >
                Thèmes
              </button>
              {openPanel === 'theme' && (
                <div className="dropdown-panel theme-selector">
                  {themes.map((theme) => (
                    <button
                      key={theme}
                      className={`tab-button ${selectedTheme === theme ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedTheme(theme);
                        setOpenPanel(null);
                      }}
                    >
                      {theme === "ALL" ? "Tous les thèmes" : theme === "OTHER" ? "AUTRES" : theme}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <button
                className={`toggle-button ${openPanel === 'phase' ? 'active' : ''}`}
                onClick={() => setOpenPanel(openPanel === 'phase' ? null : 'phase')}
              >
                Phases
              </button>
              {openPanel === 'phase' && (
                <div className="dropdown-panel">
                  {phases.map((phase) => (
                    <button
                      key={phase}
                      className={`tab-button ${selectedPhase === phase ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedPhase(phase);
                        setOpenPanel(null);
                      }}
                    >
                      {phase === "ALL" ? "Toutes les phases" : phase}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <button
                className={`toggle-button ${showingFavoritesOnly ? 'active' : ''}`}
                onClick={() => setShowingFavoritesOnly(!showingFavoritesOnly)}
              >
                Favoris
              </button>
            </div>
          </div>
          <div className="right-controls">
            <div className="execution-controls">
              <button
                className="square-btn play"
                onClick={runPipeline}
                disabled={running || jobStatus.running}
                title="Lancer 06_Executable"
              >
                <div className="play-icon" />
              </button>
              <button
                className="square-btn stop"
                onClick={stopPipeline}
                disabled={!running && !jobStatus.running}
                title="Arrêter l'exécution"
              >
                <div className="stop-icon" />
              </button>
            </div>
            <div className="status-info">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                <span style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: jobStatus.running ? '#2ecc71' : '#bdc3c7'
                }} />
                {jobStatus.running
                  ? `En cours (PID: ${jobStatus.pid})`
                  : 'Arrêté'}
              </span>
              {dataMeta?.exists && (
                <span style={{ fontSize: '12px', opacity: 0.8 }}>
                  Données maj: {new Date(dataMeta.mtime).toLocaleTimeString()} ({`${(dataMeta.size / 1024).toFixed(1)} KB`})
                </span>
              )}
            </div>
          </div>
        </div>
      </header>
      {/* Mots-clés (ouvert via le menu) */}
      {openPanel === 'keywords' && (
        <div
          className="fullscreen-panel"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(255,255,255,0.98)',
            zIndex: 9999,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
          }}
        >
          <button
            aria-label="Fermer le panneau mots-clefs"
            onClick={() => setOpenPanel(null)}
            style={{
              position: 'absolute',
              top: 20,
              right: 30,
              fontSize: 28,
              background: '#ffffff',
              border: '2px solid #ddd',
              borderRadius: '50%',
              cursor: 'pointer',
              width: '50px',
              height: '50px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#666',
              fontWeight: 'bold',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              transition: 'all 0.2s ease',
              zIndex: 10001
            }}
            onMouseEnter={(e) => {
              e.target.style.background = '#f5f5f5';
              e.target.style.transform = 'scale(1.1)';
              e.target.style.borderColor = '#999';
            }}
            onMouseLeave={(e) => {
              e.target.style.background = '#ffffff';
              e.target.style.transform = 'scale(1)';
              e.target.style.borderColor = '#ddd';
            }}
          >
            ×
          </button>
          <div style={{
            width: 'clamp(600px, 70vw, 1000px)',
            maxHeight: '85vh',
            background: '#fff',
            padding: '24px',
            borderRadius: '16px',
            overflow: 'hidden',
            boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <h2>Gestion des mots-clés</h2>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                type="text"
                placeholder="Ajouter un mot-clé…"
                value={kwInput}
                onChange={(e) => setKwInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') addKeyword(); }}
                style={{ flex: 1 }}
              />
              <button onClick={addKeyword} disabled={kwBusy}>Ajouter</button>
            </div>
            {kwError && <div style={{ color: 'crimson', marginBottom: 8 }}>{kwError}</div>}
            {keywords.length === 0 ? (
              <div style={{ opacity: 0.7 }}>Aucun mot-clé.</div>
            ) : (
              <ul
                style={{
                  maxHeight: 'calc(85vh - 200px)',
                  overflowY: 'auto',
                  margin: 0,
                  padding: 0,
                  listStyle: 'none',
                  borderTop: '1px solid #e8e8e8'
                }}
              >
                {keywords.map((k) => (
                  <li
                    key={k}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '6px 0'
                    }}
                  >
                    <span>{k}</span>
                    <button onClick={() => removeKeyword(k)} disabled={kwBusy}>Supprimer</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {/* Barre de recherche */}
      <div className="filter-bar">
        <div className="search-box">
          <input
            type="text"
            placeholder="Rechercher une entreprise..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      {/* Liste des profils */}
      <div className="profile-list">
        {filteredProfiles.map((profile, index) => (
          <div
            className={`card ${expandedIndex === index ? 'open' : ''}`}
            key={index}
            onClick={() => toggleExpand(index)}
          >
            <h2>
              <span
                className={`favorite-star ${favorites.includes(profile.post_id) ? 'favorited' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleFavorite(profile.post_id);
                }}
              >
                {favorites.includes(profile.post_id) ? '★' : '☆'}
              </span>
              #{index + 1} - {profile.company_name}
            </h2>
            <p><strong>Résumé du projet:</strong> {profile.project_summary || 'Non fourni'}</p>
            {expandedIndex === index && (
              <div className="expanded">
                <p><strong>Résumé de l'entreprise:</strong> {profile.one_sentence_description || 'Non fourni'}</p>
                <p><strong>Thème:</strong> {profile.theme || 'Non défini'}</p>
                <p><strong>Score global:</strong> {profile.score_global ?? 'N/A'}</p>
                <p><strong>Pays:</strong> {profile.location || 'N/A'}</p>
                <p><strong>Email:</strong> {profile.professional_email || 'N/A'}</p>
                <p><strong>Site web:</strong> {profile.website ? (
                  <a href={profile.website} target="_blank" rel="noreferrer">{profile.website}</a>
                ) : 'N/A'}</p>
                <p><strong>LinkedIn:</strong> {profile.profile_url ? (
                  <a href={profile.profile_url} target="_blank" rel="noreferrer">Voir le profil</a>
                ) : 'N/A'}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowActionIndex(index === showActionIndex ? null : index);
                  }}
                >
                  Action recommandée
                </button>
                {showActionIndex === index && (
                  <p>{profile.recommended_action || 'Non définie'}</p>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowReasoningIndex(index === showReasoningIndex ? null : index);
                  }}
                >
                  Voir le raisonnement
                </button>
                {showReasoningIndex === index && (
                  <p>{profile.cosma_opportunity || 'Non défini'}</p>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowIdealContactIndex(index === showIdealContactIndex ? null : index);
                  }}
                >
                  Contact idéal
                </button>
                {showIdealContactIndex === index && (
                  <p>{profile.ideal_contact || 'Non défini'}</p>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    const url = profile.post_url_x || profile.post_url;
                    if (url) {
                      window.open(url, '_blank', 'noopener,noreferrer');
                    } else {
                      alert('URL du post indisponible');
                    }
                  }}
                >
                  Voir le post LinkedIn
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      {lastRunLog && (
        <div className="logs" style={{ margin: '20px', padding: '10px', background: '#f7f7f7', borderRadius: '8px' }}>
          <h3>Logs d'exécution</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{lastRunLog}</pre>
          {jobStatus && jobStatus.returncode !== 0 && (
            <div style={{ color: 'crimson', marginTop: '8px' }}>Le script a retourné un code non nul.</div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;