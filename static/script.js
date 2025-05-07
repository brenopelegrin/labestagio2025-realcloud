document.addEventListener('DOMContentLoaded', function() {
  // Elements
  const refreshBtn = document.getElementById('refresh-btn');
  
  // Refresh button click handler - simply reloads the page to get a new recommendation
  refreshBtn.addEventListener('click', function() {
      window.location.reload();
  });
});