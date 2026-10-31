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
      if (document.getElementById('inputTargetGroup')) document.getElementById('inputTargetGroup').value = settings.target_group_url || '';
      if (document.getElementById('inputAutoLike')) document.getElementById('inputAutoLike').checked = (settings.auto_like_enabled !== '0');
      
      // Cấu hình mở rộng mới
      if (document.getElementById('inputBlacklist')) document.getElementById('inputBlacklist').value = settings.blacklist_keywords || '';
      if (document.getElementById('selectCommentMode')) document.getElementById('selectCommentMode').value = settings.comment_mode || 'both';
      if (document.getElementById('selectMaxPostAge')) document.getElementById('selectMaxPostAge').value = settings.max_post_age_hours || '24';
      if (document.getElementById('inputFanpageRotation')) document.getElementById('inputFanpageRotation').value = settings.fanpage_rotation_list || 'Vườn Phim';
      if (document.getElementById('selectRotateThreshold')) document.getElementById('selectRotateThreshold').value = settings.rotate_every_n_comments || '5';
      if (document.getElementById('inputTelegramToken')) document.getElementById('inputTelegramToken').value = settings.telegram_bot_token || '';
      if (document.getElementById('inputTelegramChatId')) document.getElementById('inputTelegramChatId').value = settings.telegram_chat_id || '';
      if (document.getElementById('inputTelegramAlerts')) document.getElementById('inputTelegramAlerts').checked = (settings.telegram_alerts_enabled === '1');

      // Cấu hình Proxy và 4 vũ khí tối ưu
      if (document.getElementById('inputProxy')) document.getElementById('inputProxy').value = settings.proxy_string || '';
      if (document.getElementById('inputLinkCloak')) document.getElementById('inputLinkCloak').checked = (settings.link_cloaking_enabled !== '0');
      if (document.getElementById('inputGeminiVision')) document.getElementById('inputGeminiVision').checked = (settings.gemini_vision_enabled !== '0');
      if (document.getElementById('inputWarmup')) document.getElementById('inputWarmup').checked = (settings.warmup_enabled !== '0');

      // Update preview lines in newsfeed
      renderSpintaxPreview(settings.spintax_samples || '');

      // Tải danh sách Fanpage đã kết nối
      await loadFanpages();
    }
  } catch (err) {
    console.error("Lỗi tải cài đặt:", err);
  }
}

// ==================== QUẢN LÝ KẾT NỐI FANPAGE ====================
async function loadFanpages() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.get_fanpages_list();
    if (res) {
      const pages = res.pages || [];
      const selected = res.selected || (pages.length > 0 ? pages[0].page_name : "Flex Phim");

      // Cập nhật Dropdown chọn tài khoản trên Newsfeed
      const selectAccount = document.getElementById('selectAccount');
      if (selectAccount && pages.length > 0) {
        selectAccount.innerHTML = pages.map(p => `
          <option value="${escapeHtml(p.page_name)}" ${p.page_name === selected ? 'selected' : ''}>
            ${escapeHtml(p.page_name)} (Đã kết nối)
          </option>
        `).join('');
      }

      // Cập nhật Huy hiệu góc dưới bên trái
      const footerName = document.getElementById('footerPageName');
      if (footerName) {
        footerName.innerText = selected;
      }

      // Render danh sách Fanpage trong tab Tài khoản & Page
      const listContainer = document.getElementById('fanpagesListContainer');
      if (listContainer) {
        if (pages.length === 0) {
          listContainer.innerHTML = '<p class="text-xs text-slate-500 italic py-2">Chưa có Fanpage nào được thêm. Hãy bấm "Tự động quét" hoặc "Thêm Fanpage thủ công".</p>';
          return;
        }
        listContainer.innerHTML = pages.map(p => `
          <div class="bg-dark-input border ${p.page_name === selected ? 'border-brand-500 bg-brand-950/20' : 'border-dark-border'} p-3 rounded-lg flex items-center justify-between transition">
            <div class="flex items-center space-x-3">
              <div class="w-8 h-8 rounded-full ${p.page_name === selected ? 'bg-brand-600 text-white' : 'bg-zinc-800 text-slate-300'} flex items-center justify-center font-bold text-xs">
                ${escapeHtml(p.page_name.substring(0, 2).toUpperCase())}
              </div>
              <div>
                <p class="text-xs font-semibold text-slate-200">${escapeHtml(p.page_name)}</p>
                <p class="text-[11px] text-slate-500 truncate max-w-xs">${escapeHtml(p.page_url || 'https://www.facebook.com')}</p>
              </div>
            </div>
            <div>
              ${p.page_name === selected ? 
                '<span class="px-2.5 py-1 text-[11px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full">● Đang đại diện cmt</span>' : 
                `<button onclick="selectActiveFanpage('${escapeHtml(p.page_name)}')" class="px-3 py-1 bg-[#252535] hover:bg-[#323245] text-slate-200 rounded text-xs border border-dark-border transition">Chọn trang này</button>`
              }
            </div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error("Lỗi tải danh sách Fanpage:", err);
  }
}

async function selectActiveFanpage(name) {
  await window.pywebview.api.select_fanpage(name);
  showToast(`Đã chọn Fanpage "${name}" làm đại diện bình luận!`);
  loadFanpages();
}

async function onAccountDropdownChange(name) {
  await window.pywebview.api.select_fanpage(name);
  showToast(`Đã chuyển sang đại diện: ${name}`);
  loadFanpages();
}

async function scanFanpagesFromFB() {
  showToast("Đang mở trình duyệt quét danh sách Fanpage...");
  const res = await window.pywebview.api.scan_fanpages_from_facebook();
  if (res && res.success) {
    showToast(`Quét hoàn tất! Tìm thấy ${res.count} Fanpage.`);
    loadFanpages();
  } else {
    showToast("Không thể quét Fanpage. Hãy đảm bảo bạn đã đăng nhập Facebook trước.", true);
  }
}

async function addManualFanpage() {
  const name = prompt("Nhập Tên Fanpage của bạn (VD: Flex Phim):");
  if (!name || !name.trim()) return;
  const url = prompt("Nhập Link Fanpage (Tùy chọn, VD: https://facebook.com/flexphim):") || "";
  const res = await window.pywebview.api.add_fanpage(name.trim(), url.trim());
  if (res && res.success) {
    showToast(`Đã kết nối Fanpage: ${res.name}`);
    loadFanpages();
  } else {
    showToast("Lỗi: " + (res ? res.message : "Không thể thêm"), true);
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
    target_group_url: document.getElementById('inputTargetGroup') ? document.getElementById('inputTargetGroup').value : '',
    auto_like_enabled: (document.getElementById('inputAutoLike') && document.getElementById('inputAutoLike').checked) ? '1' : '0',
    telegram_bot_token: document.getElementById('inputTelegramToken') ? document.getElementById('inputTelegramToken').value : '',
    telegram_chat_id: document.getElementById('inputTelegramChatId') ? document.getElementById('inputTelegramChatId').value : '',
    telegram_alerts_enabled: (document.getElementById('inputTelegramAlerts') && document.getElementById('inputTelegramAlerts').checked) ? '1' : '0',
    link_cloaking_enabled: (document.getElementById('inputLinkCloak') && document.getElementById('inputLinkCloak').checked) ? '1' : '0',
    gemini_vision_enabled: (document.getElementById('inputGeminiVision') && document.getElementById('inputGeminiVision').checked) ? '1' : '0',
    warmup_enabled: (document.getElementById('inputWarmup') && document.getElementById('inputWarmup').checked) ? '1' : '0',
  };
  await window.pywebview.api.save_settings(payload);
  showToast("Đã lưu cài đặt hệ thống & tối ưu!");
}

async function saveProxy() {
  const proxyStr = document.getElementById('inputProxy') ? document.getElementById('inputProxy').value.trim() : '';
  await window.pywebview.api.set_setting("proxy_string", proxyStr);
  showToast("Đã lưu cấu hình Proxy an toàn!");
}

async function testProxy() {
  const proxyStr = document.getElementById('inputProxy') ? document.getElementById('inputProxy').value.trim() : '';
  if (!proxyStr) {
    showToast("Vui lòng nhập chuỗi Proxy (IP:Port hoặc IP:Port:User:Pass)", true);
    return;
  }
  showToast("Đang kiểm tra kết nối qua Proxy...");
  const res = await window.pywebview.api.test_proxy(proxyStr);
  if (res && res.success) {
    showToast(res.message);
  } else {
    showToast("Lỗi Proxy: " + (res ? res.message : "Không thể kết nối"), true);
  }
}

async function testTelegram() {
  const token = document.getElementById('inputTelegramToken') ? document.getElementById('inputTelegramToken').value.trim() : '';
  const chatId = document.getElementById('inputTelegramChatId') ? document.getElementById('inputTelegramChatId').value.trim() : '';
  if (!token || !chatId) {
    showToast("Vui lòng nhập đủ Telegram Bot Token và Chat ID!", true);
    return;
  }
  showToast("Đang gửi tin nhắn test đến Telegram...");
  const res = await window.pywebview.api.test_telegram(token, chatId);
  if (res && res.success) {
    showToast("Gửi tin nhắn Telegram thành công! Hãy kiểm tra điện thoại.");
  } else {
    showToast("Lỗi gửi Telegram: " + (res ? res.message : "Không phản hồi"), true);
  }
}

async function saveRotationSettings() {
  const payload = {
    fanpage_rotation_list: document.getElementById('inputFanpageRotation').value,
    rotate_every_n_comments: document.getElementById('selectRotateThreshold').value
  };
  await window.pywebview.api.save_settings(payload);
  showToast("Đã lưu cấu hình xoay vòng Fanpage!");
}

async function saveAISettings() {
  const payload = {
    topic: document.getElementById('inputTopic').value,
    persona: document.getElementById('inputPersona').value,
    brand_mention: document.getElementById('inputBrand').value,
    keywords: document.getElementById('inputKeywords').value,
    blacklist_keywords: document.getElementById('inputBlacklist') ? document.getElementById('inputBlacklist').value : '',
    comment_mode: document.getElementById('selectCommentMode') ? document.getElementById('selectCommentMode').value : 'both',
    max_post_age_hours: document.getElementById('selectMaxPostAge') ? document.getElementById('selectMaxPostAge').value : '24',
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

async function openTargetUrlModal() {
  const input = prompt("Nhập link bài viết Facebook cần cmt (Nếu có nhiều link, có thể dán cách nhau bằng khoảng trắng hoặc xuống dòng):");
  if (input) {
    const urls = input.split(/[\s,]+/).filter(u => u.trim().startsWith("http"));
    if (urls.length > 0) {
      for (const u of urls) {
        await window.pywebview.api.add_target_url(u.trim());
      }
      showToast(`Đã thêm ${urls.length} bài viết vào danh sách cmt!`);
    } else {
      showToast("URL không hợp lệ (cần bắt đầu bằng https://...)", true);
    }
  }
}

async function exportLogsCSV() {
  showToast("Đang xuất lịch sử ra file Excel/CSV...");
  const res = await window.pywebview.api.export_csv();
  if (res && res.success) {
    showToast(`Xuất file thành công: ${res.path}`);
  } else {
    showToast("Không thể xuất file CSV", true);
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

