const state = {
  apps: [],
  reviews: [],
  snapshotDate: null,
  charts: {},
  filters: { industry: "All", app: "All" },
  view: "overall",
  focusAppKey: "com.alloapp.yump",
  sourceLabel: "Google Play · Indonesia",
  lastFetchAt: null,
  refreshTimer: null
};

const COLORS = {
  allo: "#f9c84a",
  alloSoft: "#fff1b8",
  alloBlack: "#111318",
  other: "#95c8ea",
  otherDark: "#6c97b8",
  positive: "#36a0e9",
  mixed: "#ef5f7d",
  neutral: "#ff9a3d",
  concern: "#f4c34f",
  grid: "#e9edf3"
};

const $ = id => document.getElementById(id);

const numberFmt = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0
});

const fmtNumber = value => numberFmt.format(Number(value || 0));

function fmtCompact(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}K`;
  return fmtNumber(n);
}

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
}[c]));

const pct = (n, d) => d ? Number(n || 0) / d * 100 : 0;

const appByKey = key => state.apps.find(a => a.app_key === key);
const focusApp = () => appByKey(state.focusAppKey);
const competitorApps = () => state.apps.filter(a => a.app_key !== state.focusAppKey);

function selectedApps() {
  const { industry, app } = state.filters;
  return state.apps.filter(a =>
    (industry === "All" || a.industry === industry) &&
    (app === "All" || a.app_key === app)
  );
}

function selectedReviews() {
  const { industry, app } = state.filters;
  return state.reviews.filter(r =>
    (industry === "All" || r.industry === industry) &&
    (app === "All" || r.app_key === app)
  );
}

function averageRating(apps) {
  const values = apps
    .map(a => Number(a.store_rating))
    .filter(Number.isFinite);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function aggregateReviews(rows) {
  const tone = new Map();
  const topic = new Map();

  rows.forEach(r => {
    const toneName = r.tone || "Neutral";
    const topicName = r.topic || "General";
    tone.set(toneName, (tone.get(toneName) || 0) + 1);
    topic.set(topicName, (topic.get(topicName) || 0) + 1);
  });

  return {
    total: rows.length,
    tone: [...tone].sort((a, b) => b[1] - a[1]),
    topics: [...topic].sort((a, b) => b[1] - a[1]),
    concernPct: pct(rows.filter(r => r.tone === "Concern").length, rows.length)
  };
}

function toneColor(tone) {
  return ({
    Positive: COLORS.positive,
    Mixed: COLORS.mixed,
    Neutral: COLORS.neutral,
    Concern: COLORS.concern
  })[tone] || COLORS.other;
}

function barColors(apps) {
  return apps.map(a => a.app_key === state.focusAppKey ? COLORS.allo : COLORS.other);
}

function applyDynamicHeight(canvasId, itemCount, perItem = 27, minHeight = 330) {
  const canvas = $(canvasId);
  if (!canvas?.parentElement) return;
  const height = Math.max(minHeight, Math.min(720, itemCount * perItem + 100));
  canvas.parentElement.style.height = `${height}px`;
}

function exactChartLabel(chart, active) {
  const item = active?.[0];
  return item ? String(chart.data.labels[item.index] ?? "") : "";
}

function setChartSelection(titleId, chipId, label, formatter) {
  if (!label) return;
  const title = $(titleId);
  const chip = $(chipId);
  if (title && formatter) title.textContent = formatter(label);
  if (chip) chip.textContent = `Selected · ${label}`;
}

function commonChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 180 },
    interaction: { mode: "nearest", intersect: true, axis: "xy" },
    plugins: {
      legend: { display: true, position: "bottom", labels: { usePointStyle: true, boxWidth: 8, padding: 14 } },
      tooltip: {
        mode: "nearest",
        intersect: true,
        callbacks: {
          title(items) {
            const item = items?.[0];
            return item ? String(item.chart.data.labels[item.dataIndex] ?? "") : "";
          }
        }
      }
    },
    scales: {
      y: { beginAtZero: true, grid: { color: COLORS.grid } },
      x: { grid: { display: false } }
    }
  };
}

function buildChart(key, canvasId, type, data, options = {}, onSelect = null) {
  if (state.charts[key]) state.charts[key].destroy();

  const merged = commonChartOptions();

  if (options.plugins) {
    merged.plugins = { ...merged.plugins, ...options.plugins };
  }
  if (options.scales) {
    merged.scales = { ...merged.scales, ...options.scales };
  }

  const finalOptions = {
    ...merged,
    ...options,
    onHover(event, active) {
      const nativeTarget = event?.native?.target;
      if (nativeTarget) nativeTarget.style.cursor = active?.length ? "pointer" : "default";
      options.onHover?.(event, active);
    },
    onClick(event, active) {
      if (active?.length && onSelect) {
        const label = exactChartLabel(event.chart, active);
        onSelect(label, event.chart);
      }
      options.onClick?.(event, active);
    }
  };

  state.charts[key] = new Chart($(canvasId), {
    type,
    data,
    options: finalOptions
  });
}

function populateAppFilter() {
  const select = $("appFilter");
  const current = state.filters.app;

  const ordered = [
    focusApp(),
    ...competitorApps().sort((a, b) => a.app_name.localeCompare(b.app_name))
  ].filter(Boolean);

  select.innerHTML =
    '<option value="All">All apps</option>' +
    ordered.map(a => {
      const label = a.is_focus ? "Allo Bank™ · Own App" : a.display_name || a.app_name;
      return `<option value="${esc(a.app_key)}">${esc(label)}</option>`;
    }).join("");

  if ([...select.options].some(o => o.value === current)) {
    select.value = current;
  } else {
    select.value = "All";
    state.filters.app = "All";
  }
}

function updateFilterDependentState() {
  if (state.filters.app !== "All") {
    const app = appByKey(state.filters.app);
    if (app && state.filters.industry !== "All" && app.industry !== state.filters.industry) {
      state.filters.app = "All";
      $("appFilter").value = "All";
    }
  }
}

function updateOverallTitles({ reset = true } = {}) {
  const app = state.filters.app !== "All" ? appByKey(state.filters.app) : null;
  const name = app?.display_name || app?.app_name;

  $("ratingTitle").textContent = name ? `${name} · Google Play rating` : "Current Google Play rating";
  $("reviewCountTitle").textContent = name ? `${name} · Google Play review volume` : "Google Play review volume";
  $("voiceTitle").textContent = name ? `${name} · customer voice` : "Current review signals";
  $("topicTitle").textContent = name ? `What ${name} users discuss` : "What users discuss";
  $("digitalTitle").textContent = "Digital-bank store ratings";
  $("reviewExplorerTitle").textContent = name ? `${name} · latest customer voice` : "Latest customer voice";

  if (reset) {
    $("ratingSelect").textContent = "Hover or click a bar";
    $("reviewSelect").textContent = "Log scale · hover or click";
    $("topicSelect").textContent = "Hover or click a topic";
    $("digitalSelect").textContent = "Allo Bank™ highlighted";
  }
}

function updateAlloTitles(reset = true) {
  $("alloRatingTitle").textContent = "Allo Bank™ vs. digital-bank ratings";
  $("alloReviewsTitle").textContent = "Allo Bank™ vs. digital-bank review volume";
  $("alloVoiceTitle").textContent = "Allo Bank™ review signals";
  $("alloTopicTitle").textContent = "What Allo Bank™ users discuss";
  $("alloPeerTitle").textContent = "Allo Bank™ position within digital banks";

  if (reset) {
    $("alloRatingSelect").textContent = "Hover or click";
    $("alloReviewsSelect").textContent = "Log scale · hover or click";
    $("alloTopicSelect").textContent = "Hover or click";
    $("alloPeerSelect").textContent = "Store rating benchmark";
  }
}

function renderOverall() {
  updateFilterDependentState();
  updateOverallTitles();

  const apps = selectedApps();
  const reviews = selectedReviews();
  const agg = aggregateReviews(reviews);

  const rated = apps
    .filter(a => a.store_rating != null)
    .sort((a, b) =>
      Number(b.store_rating) - Number(a.store_rating) ||
      Number(b.store_reviews_numeric || 0) - Number(a.store_reviews_numeric || 0)
    );

  const top = rated[0];
  const avg = averageRating(apps);
  const totalStoreReviews = apps.reduce((sum, a) => sum + Number(a.store_reviews_numeric || 0), 0);

  $("kpiTopRating").textContent = top ? Number(top.store_rating).toFixed(1) : "—";
  $("kpiTopRatingMeta").textContent = top ? (top.display_name || top.app_name) : "No rating available";

  $("kpiAvgRating").textContent = avg != null ? avg.toFixed(2) : "—";
  $("kpiAvgRatingMeta").textContent = `${rated.length} of ${apps.length} apps with a store rating`;

  $("kpiStoreReviews").textContent = totalStoreReviews ? fmtCompact(totalStoreReviews) : "—";
  $("kpiStoreReviewsMeta").textContent = "Displayed Google Play review volume";

  $("kpiSamples").textContent = fmtNumber(reviews.length);
  $("kpiSamplesMeta").textContent = "Customer-voice signals currently in view";

  const ratingApps = [...apps].sort((a, b) => Number(b.store_rating ?? -1) - Number(a.store_rating ?? -1));
  applyDynamicHeight("ratingChart", ratingApps.length);
  buildChart("rating", "ratingChart", "bar", {
    labels: ratingApps.map(a => a.display_name || a.app_name),
    datasets: [{
      label: "Google Play rating",
      data: ratingApps.map(a => a.store_rating == null ? null : Number(a.store_rating)),
      backgroundColor: barColors(ratingApps),
      borderRadius: 7,
      barPercentage: .78,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · rating ${Number(c.raw).toFixed(1)}`;
          }
        }
      }
    },
    scales: {
      x: {
        min: 0, max: 5,
        ticks: { stepSize: .5 },
        grid: { color: COLORS.grid },
        title: { display: true, text: "Google Play rating" }
      },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("ratingTitle", "ratingSelect", label, value => `${value} · Google Play rating`);
  });

  const reviewApps = [...apps].sort((a, b) => Number(b.store_reviews_numeric || 0) - Number(a.store_reviews_numeric || 0));
  applyDynamicHeight("storeReviewsChart", reviewApps.length);
  buildChart("storeReviews", "storeReviewsChart", "bar", {
    labels: reviewApps.map(a => a.display_name || a.app_name),
    datasets: [{
      label: "Google Play reviews",
      data: reviewApps.map(a => a.store_reviews_numeric == null ? null : Number(a.store_reviews_numeric)),
      backgroundColor: barColors(reviewApps),
      borderRadius: 7,
      barPercentage: .78,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · ${fmtCompact(c.raw)} reviews`;
          }
        }
      }
    },
    scales: {
      x: {
        type: "logarithmic",
        grid: { color: COLORS.grid },
        ticks: { callback: v => fmtCompact(v) },
        title: { display: true, text: "Displayed review count · log scale" }
      },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("reviewCountTitle", "reviewSelect", label, value => `${value} · Google Play review volume`);
  });

  const tones = ["Positive", "Mixed", "Neutral", "Concern"];
  const toneValues = tones.map(t => agg.tone.find(x => x[0] === t)?.[1] || 0);

  buildChart("tone", "toneChart", "doughnut", {
    labels: tones,
    datasets: [{
      label: "Review signals",
      data: toneValues,
      backgroundColor: tones.map(t => toneColor(t)),
      borderWidth: 2,
      borderColor: "#fff"
    }]
  }, {
    cutout: "58%",
    plugins: {
      legend: { display: true, position: "bottom" },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            const total = c.dataset.data.reduce((a, b) => a + Number(b || 0), 0);
            return `${c.label}: ${fmtNumber(c.raw)} · ${pct(c.raw, total).toFixed(1)}%`;
          }
        }
      }
    }
  });

  const topics = agg.topics.slice(0, 10);
  applyDynamicHeight("topicChart", topics.length, 31, 300);
  buildChart("topics", "topicChart", "bar", {
    labels: topics.map(x => x[0]),
    datasets: [{
      label: "Review signals",
      data: topics.map(x => x[1]),
      backgroundColor: COLORS.other,
      borderRadius: 6,
      barPercentage: .76,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · ${fmtNumber(c.raw)} signals`;
          }
        }
      }
    },
    scales: {
      x: { beginAtZero: true, grid: { color: COLORS.grid }, ticks: { precision: 0 }, title: { display: true, text: "Signals" } },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("topicTitle", "topicSelect", label, value => `Selected topic · ${value}`);
  });

  const dbApps = state.apps
    .filter(a => a.industry === "Digital Banks" && a.store_rating != null)
    .sort((a, b) => Number(b.store_rating) - Number(a.store_rating));

  applyDynamicHeight("digitalRankChart", dbApps.length, 30, 330);
  buildChart("digitalRank", "digitalRankChart", "bar", {
    labels: dbApps.map(a => a.display_name || a.app_name),
    datasets: [{
      label: "Digital-bank rating",
      data: dbApps.map(a => Number(a.store_rating)),
      backgroundColor: barColors(dbApps),
      borderRadius: 6,
      barPercentage: .76,
      categoryPercentage: .88
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · rating ${Number(c.raw).toFixed(1)}`;
          }
        }
      }
    },
    scales: {
      x: {
        min: 0, max: 5,
        ticks: { stepSize: .5 },
        grid: { color: COLORS.grid },
        title: { display: true, text: "Google Play rating" }
      },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("digitalTitle", "digitalSelect", label, value => `${value} · digital-bank rating benchmark`);
  });

  const tbody = $("appTable").querySelector("tbody");
  tbody.innerHTML = apps.length
    ? apps.slice().sort((a, b) => {
        const ar = Number(a.store_rating ?? -1), br = Number(b.store_rating ?? -1);
        return br - ar || Number(b.store_reviews_numeric || 0) - Number(a.store_reviews_numeric || 0);
      }).map(a => {
        const rs = reviews.filter(r => r.app_key === a.app_key);
        const voice = rs.length ? (aggregateReviews(rs).tone[0]?.[0] || "Neutral") : "—";
        return `<tr class="${a.is_focus ? "focus-row" : ""}" data-app="${esc(a.app_key)}">
          <td><strong>${esc(a.display_name || a.app_name)}</strong>${a.is_focus ? '<span class="own-badge">Own App</span>' : ""}</td>
          <td>${esc(a.industry)}</td>
          <td>${a.store_rating != null ? `${Number(a.store_rating).toFixed(1)} ★` : "—"}</td>
          <td>${esc(a.store_reviews_display || "—")}</td>
          <td>${esc(a.downloads_display || "—")}</td>
          <td>${rs.length ? fmtNumber(rs.length) : "—"}</td>
          <td><span class="voice-pill ${voice.toLowerCase()}">${esc(voice)}</span></td>
          <td>${esc(a.store_updated || "—")}</td>
        </tr>`;
      }).join("")
    : '<tr><td colspan="8"><div class="empty">No data for this selection.</div></td></tr>';

  $("tableNote").textContent = `${apps.length} apps`;

  const reviewList = reviews
    .slice()
    .sort((a, b) => String(b.review_date || "").localeCompare(String(a.review_date || "")))
    .slice(0, 24);

  $("reviewList").innerHTML = reviewList.length
    ? reviewList.map(r => `
      <article class="review ${r.app_key === state.focusAppKey ? "focus-review" : ""}">
        <div class="review-top">
          <div>
            <div class="review-app">${esc(r.app_name)}</div>
            <div class="review-meta">${esc(r.review_date || "Date unavailable")} · ${esc(r.reviewer_name)}</div>
          </div>
          <div class="review-stars ${String(r.tone || "").toLowerCase()}">${esc(r.tone)}</div>
        </div>
        <div class="review-text">${esc(r.review_text || "No review signal supplied.")}</div>
        <span class="issue-tag">${esc(r.topic)}</span>
        ${r.thumbs_up ? `<div class="review-meta">Helpful votes shown: ${fmtNumber(r.thumbs_up)}</div>` : ""}
      </article>`).join("")
    : '<div class="empty">No customer-voice signals for this selection.</div>';

  $("sampleNote").textContent = reviews.length
    ? `${agg.concernPct.toFixed(1)}% of the signals currently in view are tagged as concern.`
    : "No customer-voice signals are available for this selection.";
}

function renderAllo() {
  updateAlloTitles();

  const allo = focusApp();
  const peers = state.apps
    .filter(a => a.industry === "Digital Banks" && a.app_key !== state.focusAppKey && a.store_rating != null)
    .sort((a, b) => Number(b.store_rating) - Number(a.store_rating));

  const peerAvg = averageRating(peers);
  const gap = allo?.store_rating != null && peerAvg != null ? Number(allo.store_rating) - peerAvg : null;
  const alloReviews = state.reviews.filter(r => r.app_key === state.focusAppKey);
  const agg = aggregateReviews(alloReviews);

  $("alloRating").textContent = allo?.store_rating != null ? Number(allo.store_rating).toFixed(1) : "—";
  $("alloRatingMeta").textContent = allo?.store_updated ? `Last listed update · ${allo.store_updated}` : "Google Play rating";

  $("alloStoreReviews").textContent = fmtCompact(allo?.store_reviews_numeric);
  $("alloPeerAvg").textContent = peerAvg != null ? peerAvg.toFixed(2) : "—";
  $("alloGap").textContent = gap != null ? `${gap >= 0 ? "+" : ""}${gap.toFixed(2)}` : "—";
  $("alloGapMeta").textContent = gap != null
    ? `${gap >= 0 ? "Above" : "Below"} peer average · percentage points`
    : "Peer average unavailable";

  const allRank = [allo, ...peers].filter(Boolean).sort((a, b) =>
    Number(b.store_rating ?? -1) - Number(a.store_rating ?? -1)
  );

  applyDynamicHeight("alloRatingChart", allRank.length, 31, 340);
  buildChart("alloRating", "alloRatingChart", "bar", {
    labels: allRank.map(a => a.display_name || a.app_name),
    datasets: [{
      label: "Google Play rating",
      data: allRank.map(a => a.store_rating == null ? null : Number(a.store_rating)),
      backgroundColor: barColors(allRank),
      borderRadius: 7,
      barPercentage: .78,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · rating ${Number(c.raw).toFixed(1)}`;
          }
        }
      }
    },
    scales: {
      x: { min: 0, max: 5, ticks: { stepSize: .5 }, grid: { color: COLORS.grid }, title: { display: true, text: "Google Play rating" } },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("alloRatingTitle", "alloRatingSelect", label, value => `${value} · Google Play rating`);
  });

  const reviewRank = [allo, ...peers].filter(Boolean).sort((a, b) =>
    Number(b.store_reviews_numeric || 0) - Number(a.store_reviews_numeric || 0)
  );

  applyDynamicHeight("alloReviewsChart", reviewRank.length, 31, 340);
  buildChart("alloReviews", "alloReviewsChart", "bar", {
    labels: reviewRank.map(a => a.display_name || a.app_name),
    datasets: [{
      label: "Google Play reviews",
      data: reviewRank.map(a => a.store_reviews_numeric == null ? null : Number(a.store_reviews_numeric)),
      backgroundColor: barColors(reviewRank),
      borderRadius: 7,
      barPercentage: .78,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · ${fmtCompact(c.raw)} reviews`;
          }
        }
      }
    },
    scales: {
      x: {
        type: "logarithmic",
        grid: { color: COLORS.grid },
        ticks: { callback: v => fmtCompact(v) },
        title: { display: true, text: "Displayed review count · log scale" }
      },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("alloReviewsTitle", "alloReviewsSelect", label, value => `${value} · Google Play review volume`);
  });

  const tones = ["Positive", "Mixed", "Neutral", "Concern"];
  buildChart("alloTone", "alloToneChart", "doughnut", {
    labels: tones,
    datasets: [{
      label: "Allo Bank review signals",
      data: tones.map(t => agg.tone.find(x => x[0] === t)?.[1] || 0),
      backgroundColor: tones.map(t => toneColor(t)),
      borderWidth: 2,
      borderColor: "#fff"
    }]
  }, {
    cutout: "58%",
    plugins: {
      legend: { display: true, position: "bottom" },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            const total = c.dataset.data.reduce((a, b) => a + Number(b || 0), 0);
            return `${c.label}: ${fmtNumber(c.raw)} · ${pct(c.raw, total).toFixed(1)}%`;
          }
        }
      }
    }
  });

  const topics = agg.topics.slice(0, 10);
  applyDynamicHeight("alloTopicChart", topics.length, 31, 300);
  buildChart("alloTopics", "alloTopicChart", "bar", {
    labels: topics.map(x => x[0]),
    datasets: [{
      label: "Allo Bank review signals",
      data: topics.map(x => x[1]),
      backgroundColor: COLORS.allo,
      borderRadius: 6,
      barPercentage: .76,
      categoryPercentage: .9
    }]
  }, {
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title(items) {
            return items?.[0] ? String(items[0].chart.data.labels[items[0].dataIndex] ?? "") : "";
          },
          label(c) {
            return `${c.chart.data.labels[c.dataIndex]} · ${fmtNumber(c.raw)} signals`;
          }
        }
      }
    },
    scales: {
      x: { beginAtZero: true, grid: { color: COLORS.grid }, ticks: { precision: 0 }, title: { display: true, text: "Signals" } },
      y: { grid: { display: false } }
    }
  }, label => {
    setChartSelection("alloTopicTitle", "alloTopicSelect", label, value => `Selected topic · ${value}`);
  });

  const rankRows = allRank.map((a, index) => `
    <tr class="${a.app_key === state.focusAppKey ? "focus-row" : ""}">
      <td>${index + 1}</td>
      <td><strong>${esc(a.display_name || a.app_name)}</strong>${a.is_focus ? '<span class="own-badge">Own App</span>' : ""}</td>
      <td>${a.store_rating != null ? `${Number(a.store_rating).toFixed(1)} ★` : "—"}</td>
      <td>${esc(a.store_reviews_display || "—")}</td>
      <td>${esc(a.downloads_display || "—")}</td>
      <td>${a.app_key === state.focusAppKey ? "Own App" : `${(Number(a.store_rating) - Number(allo?.store_rating)).toFixed(1)} pts`}</td>
    </tr>`).join("");

  $("alloTable").querySelector("tbody").innerHTML = rankRows || '<tr><td colspan="6">No benchmark data.</td></tr>';

  const alloList = alloReviews
    .slice()
    .sort((a, b) => String(b.review_date || "").localeCompare(String(a.review_date || "")));

  $("alloReviewList").innerHTML = alloList.length
    ? alloList.map(r => `
      <article class="review focus-review">
        <div class="review-top">
          <div>
            <div class="review-app">Allo Bank™</div>
            <div class="review-meta">${esc(r.review_date || "Date unavailable")} · ${esc(r.reviewer_name)}</div>
          </div>
          <div class="review-stars ${String(r.tone || "").toLowerCase()}">${esc(r.tone)}</div>
        </div>
        <div class="review-text">${esc(r.review_text || "No review signal supplied.")}</div>
        <span class="issue-tag">${esc(r.topic)}</span>
        ${r.thumbs_up ? `<div class="review-meta">Helpful votes shown: ${fmtNumber(r.thumbs_up)}</div>` : ""}
      </article>`).join("")
    : '<div class="empty">No Allo Bank review signal is available.</div>';

  $("alloHeroDate").textContent = state.snapshotDate ? formatDate(state.snapshotDate) : "—";
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric"
  }).format(d);
}

function updateLiveClock() {
  const el = $("liveClock");
  if (!el) return;
  const now = new Date();
  el.textContent = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
  }).format(now);
}

function setRefreshButton(loading = false) {
  const button = $("refreshData");
  if (!button) return;
  button.disabled = loading;
  button.classList.toggle("is-refreshing", loading);
  button.innerHTML = loading
    ? '<span class="spin" aria-hidden="true">↻</span><span>Refreshing</span>'
    : '<span aria-hidden="true">↻</span><span>Refresh</span>';
}

function updateFeedMeta(data) {
  const dateLabel = data.ui?.last_updated_label || formatDate(data.source_snapshot_date);
  const coverage = data.ui?.coverage_label || `${state.apps.length} apps`;
  $("statusLabel").textContent = data.ui?.status_label || "Monitoring";
  $("updatedAt").textContent = state.lastFetchAt
    ? `Feed check · ${new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false }).format(state.lastFetchAt)} WIB`
    : "Feed check · —";
  $("refreshDate").textContent = dateLabel;
  $("coverageLabel").textContent = coverage;
  if ($("footerUpdate")) $("footerUpdate").textContent = `Updated ${dateLabel}`;
}

function scheduleAutoRefresh() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  state.refreshTimer = setInterval(() => load(true).catch(error => console.error("Auto-refresh failed:", error)), 5 * 60 * 1000);
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".view-tab").forEach(btn => {
    const active = btn.dataset.view === view;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });

  $("overallView").classList.toggle("active", view === "overall");
  $("alloView").classList.toggle("active", view === "allo");

  if (view === "overall") renderOverall();
  else renderAllo();
}

async function load(isAutoRefresh = false) {
  if (!isAutoRefresh) setRefreshButton(true);
  try {
    const response = await fetch(`data/dashboard_data.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Dashboard data could not be loaded (HTTP ${response.status}).`);

    const data = await response.json();

    state.apps = Array.isArray(data.apps) ? data.apps : [];
    state.reviews = Array.isArray(data.reviews) ? data.reviews : [];
    state.snapshotDate = data.source_snapshot_date || null;
    state.focusAppKey = data.focus_app_key || state.focusAppKey;
    state.sourceLabel = data.ui?.source_label || "Google Play · Indonesia";
    state.lastFetchAt = new Date();

    populateAppFilter();
    if (state.view === "overall") renderOverall();
    else renderAllo();
    updateFeedMeta(data);
    scheduleAutoRefresh();
  } finally {
    if (!isAutoRefresh) setRefreshButton(false);
  }
}

document.querySelectorAll(".view-tab").forEach(btn => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

$("industryFilter").addEventListener("change", e => {
  state.filters.industry = e.target.value;
  updateFilterDependentState();
  populateAppFilter();
  renderOverall();
});

$("appFilter").addEventListener("change", e => {
  state.filters.app = e.target.value;
  renderOverall();
});

$("resetFilters").addEventListener("click", () => {
  state.filters = { industry: "All", app: "All" };
  $("industryFilter").value = "All";
  $("appFilter").value = "All";
  renderOverall();
});

$("refreshData").addEventListener("click", () => load(false).catch(error => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div class="demo-warning"><strong>Refresh failed:</strong> ${esc(error.message)}.</div>`
  );
  console.error(error);
}));

updateLiveClock();
setInterval(updateLiveClock, 1000);

load().catch(error => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div class="demo-warning"><strong>Dashboard unavailable:</strong> ${esc(error.message)}.</div>`
  );
  console.error(error);
});
