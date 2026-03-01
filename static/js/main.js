/**
 * Checkpoint Imigrasi - Client-side Scripts
 */

document.addEventListener("DOMContentLoaded", function () {
  // ── Auto-detect search type ─────────────────────────────────────────────
  const searchInput = document.getElementById("search-query");
  const searchTypeAuto = document.getElementById("type-auto");
  const searchTypePassport = document.getElementById("type-passport");
  const searchTypeName = document.getElementById("type-name");
  const searchTypeHint = document.getElementById("search-type-hint");

  const PASSPORT_REGEX = /^[A-Z0-9]{6,12}$/;

  function detectSearchType(value) {
    const q = value.trim().toUpperCase().replace(/\s+/g, "");
    if (!value.trim()) return null;
    if (value.trim().includes(" ")) return "name";
    if (PASSPORT_REGEX.test(q)) return "passport";
    return "name";
  }

  function updateHint(value) {
    if (!searchTypeHint) return;
    if (!searchTypeAuto || !searchTypeAuto.checked) {
      searchTypeHint.textContent = "";
      return;
    }
    const detected = detectSearchType(value);
    if (detected === "passport") {
      searchTypeHint.textContent = "✓ Terdeteksi: Nomor Paspor";
      searchTypeHint.className = "form-text text-success";
    } else if (detected === "name") {
      searchTypeHint.textContent = "✓ Terdeteksi: Nama";
      searchTypeHint.className = "form-text text-info";
    } else {
      searchTypeHint.textContent = "";
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      updateHint(this.value);
    });
    // Uppercase input for passport-like queries
    searchInput.addEventListener("blur", function () {
      const detected = detectSearchType(this.value);
      if (detected === "passport") {
        this.value = this.value.trim().toUpperCase();
      }
    });
  }

  // ── Flash message auto-dismiss ──────────────────────────────────────────
  const alerts = document.querySelectorAll(".alert.alert-dismissible");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });

  // ── Search form loading state ───────────────────────────────────────────
  const searchForm = document.getElementById("search-form");
  const searchBtn = document.getElementById("search-btn");

  if (searchForm && searchBtn) {
    searchForm.addEventListener("submit", function () {
      searchBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Mencari...';
      searchBtn.disabled = true;
    });
  }
});
