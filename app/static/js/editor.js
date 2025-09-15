document.addEventListener("DOMContentLoaded", () => {
    // Edit-Button
    const editBtn = document.getElementById("edit-btn");
    const preview = document.getElementById("generated-preview");
    const editForm = document.getElementById("edit-form");

    if (editBtn && preview && editForm) {
        editBtn.addEventListener("click", () => {
            preview.style.display = "none";
            editForm.style.display = "block";
        });
    }

    // Quill-Editor
    const editorEl = document.getElementById("editor");
    if (editorEl) {
        const quill = new Quill(editorEl, {
            theme: "snow",
            placeholder: "Write your email...",
            modules: {
                toolbar: [
                    [{ font: [] }, { size: [] }],
                    ["bold", "italic", "underline", "strike"],
                    [{ color: [] }, { background: [] }],
                    [{ align: [] }],
                    ["link", "image"],
                    ["clean"]
                ]
            }
        });

        // Sync Quill content into hidden input before submit
        editForm?.addEventListener("submit", function () {
            const hiddenInput = document.createElement("input");
            hiddenInput.type = "hidden";
            hiddenInput.name = "edited_message";
            hiddenInput.value = quill.root.innerHTML;
            editForm.appendChild(hiddenInput);
        });
    }

    // Toggle Cc/Bcc
    const toggle = document.getElementById("toggle-cc-bcc");
    const ccBccRow = document.getElementById("cc-bcc-row");

    if (toggle && ccBccRow) {
        toggle.addEventListener("click", () => {
            ccBccRow.style.display =
                ccBccRow.style.display === "none" ? "block" : "none";
        });
    }
});
