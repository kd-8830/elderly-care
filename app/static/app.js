// Stage 1: no client-side behaviour required.
// Shared helpers (speech, dose checklist) land in later stages.


// ---------------- Stage 8: read-aloud ----------------
function readSchedule() {
  var el = document.getElementById('schedule-text');
  if (!el || !('speechSynthesis' in window)) {
    alert('Read-aloud is not supported in this browser.');
    return;
  }
  window.speechSynthesis.cancel();
  var utter = new SpeechSynthesisUtterance(el.textContent.trim());
  utter.rate = 0.9;
  utter.pitch = 1.0;
  window.speechSynthesis.speak(utter);
}