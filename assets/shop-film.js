(() => {
  const video = document.querySelector('.medicine-film');
  const button = document.querySelector('.film-control');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  function syncControl() {
    button.querySelector('[lang=en]').textContent = video.paused ? 'Play animation' : 'Pause animation';
    button.querySelector('[lang=ur]').textContent = video.paused ? 'اینیمیشن چلائیں' : 'اینیمیشن روکیں';
  }
  function play() {
    if (!video.hasAttribute('src')) video.src = video.dataset.src;
    video.play().catch(syncControl);
  }
  function applyPreference() {
    if (motion.matches || navigator.connection?.saveData) video.pause();
    else play();
    syncControl();
  }
  button.hidden = false;
  button.addEventListener('click', () => video.paused ? play() : video.pause());
  video.addEventListener('play', syncControl);
  video.addEventListener('pause', syncControl);
  video.addEventListener('error', () => { button.hidden = true; });
  motion.addEventListener('change', applyPreference);
  applyPreference();
})();