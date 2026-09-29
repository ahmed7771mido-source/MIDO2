// ========== AI Chatbot ==========
var cbIsOpen = false;
var cbHistory = [];

var cbBtn = document.getElementById('chatbot-btn');
var cbPanel = document.getElementById('chatbot-panel');
var cbClose = document.getElementById('cb-close');
var cbForm = document.getElementById('cb-form');
var cbInput = document.getElementById('cb-input');
var cbMsgs = document.getElementById('cb-msgs');

// فتح / إغلاق
cbBtn.addEventListener('click', function () {
  cbIsOpen = !cbIsOpen;
  cbPanel.classList.toggle('open', cbIsOpen);
  if (cbIsOpen) {
    document.querySelector('#chatbot-btn .chat-dot').style.display = 'none';
    cbInput.focus();
  }
});

cbClose.addEventListener('click', function () {
  cbIsOpen = false;
  cbPanel.classList.remove('open');
});

// الأزرار السريعة
function cbQuick(text) {
  cbInput.value = text;
  cbSend(text);
}

// إرسال رسالة
cbForm.addEventListener('submit', function (e) {
  e.preventDefault();
  var msg = cbInput.value.trim();
  if (!msg) return;
  cbInput.value = '';
  cbSend(msg);
});

function cbSend(msg) {
  cbAddMsg(msg, 'user');
  var tid = cbTyping();

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg, history: cbHistory })
  })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      cbRemoveTyping(tid);
      var reply = (d && d.response) ? d.response : 'عذراً، حدث خطأ. حاول مرة أخرى.';
      cbAddMsg(reply, 'bot');
      cbHistory.push({ role: 'user', content: msg });
      cbHistory.push({ role: 'assistant', content: reply });
      if (cbHistory.length > 10) cbHistory = cbHistory.slice(-10);
    })
    .catch(function () {
      cbRemoveTyping(tid);
      cbAddMsg('عذراً، تعذّر الاتصال. حاول مرة أخرى.', 'bot');
    });
}

function cbAddMsg(text, type) {
  var av = type === 'bot' ? '🤖' : '👤';
  var div = document.createElement('div');
  div.className = 'cb-msg ' + type;
  div.innerHTML = '<div class="cb-msg-av">' + av + '</div>'
    + '<div class="cb-msg-txt">' + cbFmt(text) + '</div>';
  cbMsgs.appendChild(div);
  cbMsgs.scrollTop = cbMsgs.scrollHeight;
}

function cbTyping() {
  var id = 'cbt_' + Date.now();
  var div = document.createElement('div');
  div.id = id;
  div.className = 'cb-msg bot';
  div.innerHTML = '<div class="cb-msg-av">🤖</div>'
    + '<div class="cb-msg-txt"><div class="cb-typing">'
    + '<span></span><span></span><span></span></div></div>';
  cbMsgs.appendChild(div);
  cbMsgs.scrollTop = cbMsgs.scrollHeight;
  return id;
}

function cbRemoveTyping(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}

function cbFmt(t) {
  return t.replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}
