document.addEventListener("DOMContentLoaded", function () {
  var fileInput = document.getElementById("pdf-input");
  var compressBtn = document.getElementById("compress-btn");
  var btnText = document.getElementById("btn-text");
  var btnSpinner = document.getElementById("btn-spinner");
  var preview = document.getElementById("file-preview");
  var previewName = document.getElementById("preview-name");
  var previewSize = document.getElementById("preview-size");
  var errorArea = document.getElementById("error-area");

  if (!fileInput || !compressBtn) {
    return;
  }

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
      compressBtn.disabled = true;
      if (btnText) btnText.textContent = "Compressing…";
      if (btnSpinner) btnSpinner.classList.remove("hidden");
    } else {
      // Re-enable only if file is selected
      var hasFile = fileInput.files && fileInput.files.length > 0;
      compressBtn.disabled = !hasFile;
      if (btnText) btnText.textContent = "Compress PDF";
      if (btnSpinner) btnSpinner.classList.add("hidden");
    }
  }

  // File input change: light client-side sanity check, show preview, enable button
  fileInput.addEventListener("change", function () {
    clearError();
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      if (preview) preview.classList.add("hidden");
      compressBtn.disabled = true;
      return;
    }

    // Extension check
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please select a PDF file (.pdf).");
      if (preview) preview.classList.add("hidden");
      compressBtn.disabled = true;
      return;
    }

    // Show preview
    if (previewName) previewName.textContent = file.name;
    if (previewSize) previewSize.textContent = formatSize(file.size);
    if (preview) preview.classList.remove("hidden");

    compressBtn.disabled = false;
  });

  // Compress click: fetch POST
  compressBtn.addEventListener("click", function () {
    clearError();
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError("Please select a PDF file first.");
      return;
    }

    // Final extension sanity check
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please select a PDF file (.pdf).");
      return;
    }

    var formData = new FormData();
    formData.append("file", file);

    setLoading(true);

    fetch("/compress-pdf", {
      method: "POST",
      body: formData,
    })
      .then(function (response) {
        if (response.ok) {
          // Try to get filename from Content-Disposition
          var disposition = response.headers.get("Content-Disposition") || "";
          var filename = "compressed-" + file.name;
          try {
            // disposition may be like: attachment; filename="compressed-foo.pdf" or filename*=UTF-8''...
            var match = /filename\*?=(?:UTF-8''?)?\"?([^\";]+)\"?/i.exec(disposition);
            if (match && match[1]) {
              // decode RFC5987 if needed
              try {
                filename = decodeURIComponent(match[1]);
              } catch (e) {
                filename = match[1];
              }
            }
          } catch (e) {
            // fall back to default
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
          // Failure: parse JSON error body
          return response
            .json()
            .then(function (data) {
              var msg = (data && data.error) || "An error occurred while compressing the PDF.";
              showError(msg);
            })
            .catch(function () {
              showError("An error occurred while compressing the PDF. Please try again.");
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
