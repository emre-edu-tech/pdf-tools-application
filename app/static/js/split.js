document.addEventListener("DOMContentLoaded", function () {
  var fileInput = document.getElementById("pdf-input");
  var splitBtn = document.getElementById("split-btn");
  var btnText = document.getElementById("btn-text");
  var btnSpinner = document.getElementById("btn-spinner");
  var preview = document.getElementById("file-preview");
  var previewName = document.getElementById("preview-name");
  var previewSize = document.getElementById("preview-size");
  var errorArea = document.getElementById("error-area");
  var fromInput = document.getElementById("from-page");
  var toInput = document.getElementById("to-page");

  if (!fileInput || !splitBtn) {
    return;
  }

  var MAX_BYTES = 50 * 1024 * 1024; // 50 MB — keep in sync with app/config.py & .env.example

  function showError(msg) {
    if (!errorArea) return;
    errorArea.textContent = msg;
    errorArea.classList.remove("hidden");
  }

  function clearError() {
    if (!errorArea) return;
    errorArea.textContent = "";
    errorArea.classList.add("hidden");
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function setLoading(isLoading) {
    if (isLoading) {
      splitBtn.disabled = true;
      if (btnText) btnText.textContent = "Splitting…";
      if (btnSpinner) btnSpinner.classList.remove("hidden");
    } else {
      var hasFile = fileInput.files && fileInput.files.length > 0;
      var oversized = hasFile && fileInput.files[0].size > MAX_BYTES;
      splitBtn.disabled = !hasFile || oversized;
      if (btnText) btnText.textContent = "Split PDF";
      if (btnSpinner) btnSpinner.classList.add("hidden");
    }
  }

  function validatePageInputs(showEmptyError) {
    var fromVal = fromInput ? fromInput.value.trim() : "";
    var toVal = toInput ? toInput.value.trim() : "";

    if (!fromVal || !toVal) {
      if (showEmptyError) {
        return "Please enter both 'From page' and 'To page'.";
      }
      return null;
    }

    // Must be whole numbers (positive integers)
    var wholeNumberPattern = /^\d+$/;
    if (!wholeNumberPattern.test(fromVal) || !wholeNumberPattern.test(toVal)) {
      return "'From page' and 'to page' must be whole numbers.";
    }

    var fromNum = parseInt(fromVal, 10);
    var toNum = parseInt(toVal, 10);

    if (fromNum < 1) {
      return "'From page' must be at least 1.";
    }
    if (toNum < 1) {
      return "'To page' must be at least 1.";
    }
    if (fromNum > toNum) {
      return "'From page' can't be greater than 'to page'.";
    }
    return null;
  }

  function handlePageBlur() {
    var msg = validatePageInputs(false);
    if (msg) {
      showError(msg);
    } else {
      // Only clear if error was a page validation error; but we clear generally
      // to allow user to correct. We check if there is no other error pending.
      // Simpler: clear if validation passes and no file error is present.
      var currentError = errorArea ? errorArea.textContent : "";
      // Clear if current error matches any page validation message
      if (
        currentError &&
        (currentError.indexOf("From page") !== -1 ||
          currentError.indexOf("To page") !== -1 ||
          currentError.indexOf("whole numbers") !== -1 ||
          currentError.indexOf("Please enter both") !== -1)
      ) {
        clearError();
      }
    }
  }

  if (fromInput) {
    fromInput.addEventListener("blur", handlePageBlur);
    fromInput.addEventListener("input", function () {
      // Clear page-related error on typing
      if (errorArea && !errorArea.classList.contains("hidden")) {
        var current = errorArea.textContent;
        if (
          current.indexOf("From page") !== -1 ||
          current.indexOf("To page") !== -1 ||
          current.indexOf("whole numbers") !== -1
        ) {
          clearError();
        }
      }
    });
  }

  if (toInput) {
    toInput.addEventListener("blur", handlePageBlur);
    toInput.addEventListener("input", function () {
      if (errorArea && !errorArea.classList.contains("hidden")) {
        var current = errorArea.textContent;
        if (
          current.indexOf("From page") !== -1 ||
          current.indexOf("To page") !== -1 ||
          current.indexOf("whole numbers") !== -1
        ) {
          clearError();
        }
      }
    });
  }

  // File input change: light client-side sanity check, show preview, enable button
  fileInput.addEventListener("change", function () {
    clearError();
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      if (preview) preview.classList.add("hidden");
      splitBtn.disabled = true;
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please select a PDF file (.pdf).");
      if (preview) preview.classList.add("hidden");
      splitBtn.disabled = true;
      return;
    }

    // Client-side size check — instant feedback, no network round trip
    if (file.size > MAX_BYTES) {
      showError("File is too large (" + formatSize(file.size) + "). Maximum allowed size is 50 MB.");
      if (preview) preview.classList.add("hidden");
      splitBtn.disabled = true;
      return;
    }

    if (previewName) previewName.textContent = file.name;
    if (previewSize) previewSize.textContent = formatSize(file.size);
    if (preview) preview.classList.remove("hidden");

    // Check page inputs if already filled
    var pageError = validatePageInputs(false);
    if (pageError) {
      showError(pageError);
    }

    splitBtn.disabled = false;
  });

  // Split click: validate client-side then fetch POST
  splitBtn.addEventListener("click", function () {
    clearError();
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError("Please select a PDF file first.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please select a PDF file (.pdf).");
      return;
    }

    // Defensive second gate for size
    if (file.size > MAX_BYTES) {
      showError("File is too large (" + formatSize(file.size) + "). Maximum allowed size is 50 MB.");
      return;
    }

    var pageError = validatePageInputs(true);
    if (pageError) {
      showError(pageError);
      return;
    }

    var fromVal = fromInput.value.trim();
    var toVal = toInput.value.trim();

    var formData = new FormData();
    formData.append("file", file);
    formData.append("from_page", fromVal);
    formData.append("to_page", toVal);

    setLoading(true);

    fetch("/split-pdf", {
      method: "POST",
      body: formData,
    })
      .then(function (response) {
        if (response.ok) {
          var disposition = response.headers.get("Content-Disposition") || "";
          var filename = "split-" + fromVal + "-" + toVal + "-" + file.name;
          try {
            var match = /filename\*?=(?:UTF-8''?)?\"?([^\";]+)\"?/i.exec(disposition);
            if (match && match[1]) {
              try {
                filename = decodeURIComponent(match[1]);
              } catch (e) {
                filename = match[1];
              }
            }
          } catch (e) {
            // fall back
          }

          return response.blob().then(function (blob) {
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(function () {
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            }, 1000);
          });
        } else {
          if (response.status === 413) {
            return response
              .json()
              .then(function (data) {
                var msg = (data && data.error) || "File is too large. Maximum allowed size is 50 MB.";
                showError(msg);
              })
              .catch(function () {
                showError("File is too large. Maximum allowed size is 50 MB.");
              });
          }
          return response
            .json()
            .then(function (data) {
              var msg = (data && data.error) || "An error occurred while splitting the PDF.";
              showError(msg);
            })
            .catch(function () {
              showError("An error occurred while splitting the PDF. Please try again.");
            });
        }
      })
      .catch(function () {
        showError("Network error. Please check your connection and try again.");
      })
      .finally(function () {
        setLoading(false);
      });
  });
});
