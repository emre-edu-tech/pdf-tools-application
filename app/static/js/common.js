document.addEventListener("DOMContentLoaded", function () {
  // Mobile nav toggle
  var toggle = document.getElementById("nav-toggle");
  var menu = document.getElementById("mobile-menu");
  var iconOpen = document.getElementById("nav-icon-open");
  var iconClose = document.getElementById("nav-icon-close");

  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var isHidden = menu.classList.contains("hidden");
      menu.classList.toggle("hidden");
      toggle.setAttribute("aria-expanded", String(isHidden));
      if (iconOpen) iconOpen.classList.toggle("hidden");
      if (iconClose) iconClose.classList.toggle("hidden");
    });
  }

  // Flash auto-dismiss after ~5s + manual dismiss
  var flashes = document.querySelectorAll(".flash-message");
  flashes.forEach(function (el) {
    var timeout = setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 500);
    }, 5000);

    var closeBtn = el.querySelector(".flash-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        clearTimeout(timeout);
        el.style.opacity = "0";
        setTimeout(function () {
          el.remove();
        }, 300);
      });
    }
  });
});
