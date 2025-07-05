/* Example: simple form thank-you without page reload */
document.addEventListener('submit', async (e) => {
  if (e.target.matches('.demo__form')) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    const res  = await fetch(form.action, { method: 'POST', body: data, headers: { 'Accept': 'application/json' } });
    if (res.ok) {
      form.innerHTML = '<h3>Thank you! We’ll reach out shortly.</h3>';
    } else {
      alert('Oops! Something went wrong. Please email us directly.');
    }
  }
});
