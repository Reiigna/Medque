// Smart auto-refresh — pauses when user is typing in any input
let userTyping = false;
let typingTimer;
let refreshInterval;

function startRefreshTimer() {
  refreshInterval = setInterval(() => {
    if (!userTyping) {
      fetchQueueUpdate();
    }
  }, 10000);
}

// Detect typing in any input/select/textarea
document.addEventListener('input', () => {
  userTyping = true;
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    userTyping = false;
  }, 3000); // stops being "typing" 3 seconds after last keystroke
});

document.addEventListener('change', () => {
  userTyping = true;
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    userTyping = false;
  }, 3000);
});

// Update the countdown display without reloading
function fetchQueueUpdate() {
  fetch('/api/queue')
    .then(r => r.json())
    .then(data => {
      // Update queue length stat if element exists
      const ql = document.getElementById('live-queue-length');
      if (ql) ql.textContent = data.queue_length;

      // Update current patient if element exists
      const cp = document.getElementById('live-current-patient');
      if (cp && data.current) cp.textContent = data.current.name;

      // Update pending appointments count
      const pa = document.getElementById('live-pending-appts');
      // handled by full reload below for secretary
    })
    .catch(() => {}); // silent fail
}

// Countdown display
let secondsLeft = 10;
const countEl = document.getElementById('refresh-count');

function updateCountdown() {
  if (countEl) countEl.textContent = secondsLeft;
  secondsLeft--;
  if (secondsLeft < 0) {
    secondsLeft = 10;
    if (!userTyping) {
      location.reload();
    } else {
      // Reset countdown but don't reload since user is typing
      secondsLeft = 10;
    }
  }
}

setInterval(updateCountdown, 1000);