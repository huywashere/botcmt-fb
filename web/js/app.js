// Global State
let currentTab = 'newsfeed';
let selectedPost = null;
let currentLogs = [];

// Clock update
setInterval(() => {
  const now = new Date();
  document.getElementById('headerClock').innerText = now.toLocaleTimeString('vi-VN') + ' UTC+7';
}, 1000);

// Tab switching
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(el => {
    el.classList.remove('active-nav', 'text-white', 'bg-dark-hover', 'border-l-4', 'border-brand-500');
    el.classList.add('text-slate-400');
  });

  const activeContent = document.getElementById(`tab-content-${tabId}`);
  if (activeContent) activeContent.classList.remove('hidden');

  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('active-nav', 'text-white', 'bg-dark-hover', 'border-l-4', 'border-brand-500');
    activeBtn.classList.remove('text-slate-400');
  }
}

// Toast notification
function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  toast.innerText = msg;
  toast.classList.remove('hidden', 'border-brand-500', 'border-red-500');
  toast.classList.add(isError ? 'border-red-500' : 'border-brand-500');
  setTimeout(() => toast.classList.add('hidden'), 3500);
}

// Load initial configuration
async function loadConfig() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const settings = await window.pywebview.api.get_settings();
    if (settings) {
      if (document.getElementById('inputTopic')) document.getElementById('inputTopic').value = settings.topic || '';
      if (document.getElementById('inputPersona')) document.getElementById('inputPersona').value = settings.persona || '';
      if (document.getElementById('inputBrand')) document.getElementById('inputBrand').value = settings.brand_mention || '';
      if (document.getElementById('inputKeywords')) document.getElementById('inputKeywords').value = settings.keywords || '';
      if (document.getElementById('inputSpintax')) document.getElementById('inputSpintax').value = settings.spintax_samples || '';
      if (document.getElementById('inputGeminiKey')) document.getElementById('inputGeminiKey').value = settings.gemini_api_key || '';
      if (document.getElementById('inputMinDelay')) document.getElementById('inputMinDelay').value = settings.min_delay || '120';
      if (document.getElementById('inputMaxDelay')) document.getElementById('inputMaxDelay').value = settings.max_delay || '300';
      if (document.getElementById('inputDailyLimit')) document.getElementById('inputDailyLimit').value = settings.daily_limit || '25';
      if (document.getElementById('inputSessionDuration')) document.getElementById('inputSessionDuration').value = settings.session_duration_minutes || '0';
      if (document.getElementById('inputActiveStart')) document.getElementById('inputActiveStart').value = settings.active_start || '08:00';
      if (document.getElementById('inputActiveEnd')) document.getElementById('inputActiveEnd').value = settings.active_end || '23:00';

      // Update preview lines in newsfeed
      renderSpintaxPreview(settings.spintax_samples || '');
    }
  } catch (err) {
    console.error("Lỗi tải cài đặt:", err);
  }
}

function renderSpintaxPreview(spintaxText) {
  const previewDiv = document.getElementById('spintaxPreviewLines');
  const lines = spintaxText.split('\n').filter(l => l.trim().length > 0);
  if (lines.length === 0) {
    previewDiv.innerHTML = '<span class="text-slate-500">Chưa thiết lập mẫu bình luận hoặc kịch bản AI.</span>';
    return;
  }
  previewDiv.innerHTML = lines.slice(0, 3).map(l => `<div class="truncate">${escapeHtml(l)}</div>`).join('');
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Test Gemini API Key
async function testGemini() {
  const geminiText = document.getElementById('geminiText');
  const geminiBadge = document.getElementById('geminiBadge');
  geminiText.innerText = 'Đang kiểm tra...';

  try {
    const key = document.getElementById('inputGeminiKey') ? document.getElementById('inputGeminiKey').value : '';
    const res = await window.pywebview.api.test_gemini(key);
    if (res.success) {
      geminiText.innerText = 'Gemini Đã kết nối';
      geminiBadge.classList.remove('text-amber-300');
      geminiBadge.classList.add('text-emerald-400');
      showToast("Kết nối Gemini AI thành công!");
    } else {
      geminiText.innerText = 'Gemini Lỗi: ' + res.message;
      geminiBadge.classList.remove('text-emerald-400');
      geminiBadge.classList.add('text-amber-300');
      showToast("Lỗi: " + res.message, true);
    }
  } catch (err) {
    geminiText.innerText = 'Lỗi kết nối';
    showToast("Không thể kiểm tra API", true);
  }
}

// Save Settings
async function saveAllSettings() {
  const payload = {
    gemini_api_key: document.getElementById('inputGeminiKey').value,
    min_delay: document.getElementById('inputMinDelay').value,
    max_delay: document.getElementById('inputMaxDelay').value,
    daily_limit: document.getElementById('inputDailyLimit').value,
    session_duration_minutes: document.getElementById('inputSessionDuration').value,
    active_start: document.getElementById('inputActiveStart').value,
    active_end: document.getElementById('inputActiveEnd').value,
  };
  await window.pywebview.api.save_settings(payload);
  showToast("Đã lưu cài đặt hệ thống!");
}

async function saveAISettings() {
  const payload = {
    topic: document.getElementById('inputTopic').value,
    persona: document.getElementById('inputPersona').value,
    brand_mention: document.getElementById('inputBrand').value,
    keywords: document.getElementById('inputKeywords').value,
    spintax_samples: document.getElementById('inputSpintax').value
  };
  await window.pywebview.api.save_settings(payload);
  renderSpintaxPreview(payload.spintax_samples);
  showToast("Đã lưu kịch bản AI thành công!");
}

// Actions
async function runScanOnly() {
  showToast("Đang bắt đầu quét thử Newsfeed...");
  await window.pywebview.api.scan_test();
}

async function toggleAutoComment() {
  showToast("Đang bật chế độ tự động bình luận...");
  await window.pywebview.api.start_auto();
}

async function stopAutoComment() {
  showToast("Đang dừng tác vụ...");
  await window.pywebview.api.stop_auto();
}

async function openLoginBrowser() {
  showToast("Đang mở trình duyệt đăng nhập Facebook...");
  await window.pywebview.api.open_login_browser();
}

async function checkLoginStatus() {
  const indicator = document.getElementById('loginStatusIndicator');
  indicator.innerText = "Đang kiểm tra...";
  const res = await window.pywebview.api.check_login_status();
  if (res.is_logged_in) {
    indicator.innerHTML = '<span class="text-emerald-400 font-semibold">● Đã đăng nhập Facebook</span>';
  } else {
    indicator.innerHTML = '<span class="text-amber-400 font-semibold">● Chưa đăng nhập. Hãy bấm mở trình duyệt để đăng nhập.</span>';
  }
}

function updateInterval(val) {
  window.pywebview.api.set_setting("scan_interval", val);
  showToast(`Đã đổi tần suất quét mỗi ${val} phút`);
}

function updateFeedSource(val) {
  window.pywebview.api.set_setting("feed_source", val);
  showToast(`Đã đổi nguồn bài viết: ${val}`);
}

function openTargetUrlModal() {
  const url = prompt("Nhập link bài viết Facebook hoặc Group cần quét:");
  if (url) {
    window.pywebview.api.add_target_url(url);
    showToast("Đã thêm URL vào danh sách quét!");
  }
}

// Inspector & Details
function selectPostRow(index) {
  const post = currentLogs[index];
  if (!post) return;
  selectedPost = post;

  // Highlight selected row
  document.querySelectorAll('#logsTableBody tr').forEach((tr, i) => {
    if (i === index) {
      tr.classList.add('bg-brand-900/40', 'border-brand-500');
    } else {
      tr.classList.remove('bg-brand-900/40', 'border-brand-500');
    }
  });

  document.getElementById('selectedPostSnippet').innerText = post.post_snippet || post.content || 'Nội dung bài viết...';
  document.getElementById('selectedCommentText').value = post.comment_content || post.predicted_comment || '';
}

function openOriginalUrl() {
  if (selectedPost && selectedPost.post_url) {
    window.pywebview.api.open_url_external(selectedPost.post_url);
  } else {
    showToast("Vui lòng chọn 1 bài viết trước", true);
  }
}

async function sendManualComment() {
  if (!selectedPost || !selectedPost.post_url) {
    showToast("Chưa chọn bài viết để gửi", true);
    return;
  }
  const commentText = document.getElementById('selectedCommentText').value;
  if (!commentText.trim()) {
    showToast("Nội dung bình luận không được để trống", true);
    return;
  }
  showToast("Đang gửi bình luận...");
  const res = await window.pywebview.api.send_manual_comment(selectedPost.post_url, commentText);
  if (res.success) {
    showToast("Bình luận thành công!");
  } else {
    showToast("Lỗi: " + res.message, true);
  }
}

// Polling State Updates from Python Backend
async function pollBackendState() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const state = await window.pywebview.api.get_state();
    if (state) {
      // Live Status
      if (document.getElementById('statusLiveText')) {
        document.getElementById('statusLiveText').innerText = state.live_status || 'Sẵn sàng hoạt động.';
      }

      // Countdown
      if (document.getElementById('countdownTimer')) {
        document.getElementById('countdownTimer').innerText = state.countdown || '';
      }

      // Auto comment state badge
      const autoPill = document.getElementById('autoStatusPill');
      const btnAutoToggle = document.getElementById('btnAutoToggle');
      if (state.is_auto_running) {
        autoPill.innerText = 'Đã bật';
        autoPill.className = 'px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800 animate-pulse';
        btnAutoToggle.innerText = 'Đang tự bình luận...';
        btnAutoToggle.classList.add('opacity-75');
      } else {
        autoPill.innerText = 'Đang dừng';
        autoPill.className = 'px-2.5 py-1 rounded-full text-[11px] font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700';
        btnAutoToggle.innerText = 'Bật tự bình luận';
        btnAutoToggle.classList.remove('opacity-75');
      }

      // Render Logs Table
      if (state.logs && JSON.stringify(state.logs) !== JSON.stringify(currentLogs)) {
        currentLogs = state.logs;
        renderLogsTable(currentLogs);
      }

      // Update counters
      if (document.getElementById('totalCommentedBadge')) {
        document.getElementById('totalCommentedBadge').innerText = `${currentLogs.length} bài viết`;
      }
      if (document.getElementById('statTodayCount')) {
        document.getElementById('statTodayCount').innerText = state.today_count || '0';
      }
    }
  } catch (err) {
    console.error("Lỗi polling state:", err);
  }
}

function renderLogsTable(logs) {
  const tbody = document.getElementById('logsTableBody');
  if (!tbody) return;

  if (logs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="3" class="py-6 text-center text-slate-500 italic">
          Chưa có bài viết nào được quét. Hãy bấm "Quét thử - chưa gửi" hoặc "Bật tự bình luận".
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = logs.map((log, index) => {
    let statusClass = "bg-zinc-800 text-zinc-400 border-zinc-700";
    if (log.status === 'Đã gửi') {
      statusClass = "bg-emerald-950 text-emerald-400 border-emerald-800";
    } else if (log.status === 'Lỗi') {
      statusClass = "bg-red-950 text-red-400 border-red-800";
    } else if (log.status.includes('Quét thử')) {
      statusClass = "bg-amber-950 text-amber-300 border-amber-800";
    }

    return `
      <tr onclick="selectPostRow(${index})" class="hover:bg-dark-hover cursor-pointer transition border-b border-dark-border/40">
        <td class="py-2.5 px-3 max-w-[220px] truncate text-slate-300 font-medium">
          ${escapeHtml(log.post_snippet || log.content || 'Bài viết Facebook')}
        </td>
        <td class="py-2.5 px-3 max-w-[260px] truncate text-slate-400 font-sans">
          ${escapeHtml(log.comment_content || log.predicted_comment || '')}
        </td>
        <td class="py-2.5 px-3 text-right">
          <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusClass}">
            ${escapeHtml(log.status)}
          </span>
        </td>
      </tr>
    `;
  }).join('');
}

// Window ready initialization
window.addEventListener('pywebviewready', () => {
  loadConfig();
  // Poll state every 1.5 seconds
  setInterval(pollBackendState, 1500);
});

