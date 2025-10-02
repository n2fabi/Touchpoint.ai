// static/js/editor.js
document.addEventListener("DOMContentLoaded", () => {
  const editorEl = document.getElementById("editor");
  const hiddenInput = document.getElementById("body_html");
  const editForm = document.getElementById("edit-form");

  if (editorEl) {
    tinymce.init({
      selector: '#editor',
      menubar: false,
      plugins: 'lists link image table code',
      toolbar: 'undo redo | fontselect fontsizeselect | bold italic underline strikethrough | forecolor backcolor | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | link image table | code',

      // 🎨 E-Mail-Safe Fonts
      font_formats:
        'Arial=Arial,Helvetica,sans-serif;' +
        'Arial Black="Arial Black",Gadget,sans-serif;' +
        'Comic Sans MS="Comic Sans MS",cursive,sans-serif;' +
        'Courier New="Courier New",Courier,monospace;' +
        'Georgia=Georgia,serif;' +
        'Impact=Impact,Charcoal,sans-serif;' +
        'Tahoma=Tahoma,Geneva,sans-serif;' +
        '"Times New Roman"="Times New Roman",Times,serif;' +
        'Trebuchet MS="Trebuchet MS",Helvetica,sans-serif;' +
        'Verdana=Verdana,Geneva,sans-serif;',

      valid_elements: '*[*]',
      extended_valid_elements: 'span[style],p[style],div[style]',
      content_css: false,
      content_style: 'body { margin: 8px; }',
      forced_root_block: 'p',

      setup: (editor) => {
        editor.on('init', () => {
          const initialHtml = editorEl.dataset.initialContent || "";
          if (initialHtml) {
            editor.setContent(initialHtml, { format: 'raw' });
          }
        });

        if (editForm && hiddenInput) {
          editForm.addEventListener('submit', () => {
            hiddenInput.value = editor.getContent();
          });
        }
      }
    });
  }

  // Toggle Cc/Bcc
  const toggle = document.getElementById("toggle-cc-bcc");
  const ccBccRow = document.getElementById("cc-bcc-row");
  if (toggle && ccBccRow) {
    toggle.addEventListener("click", () => {
      ccBccRow.style.display = ccBccRow.style.display === "none" ? "block" : "none";
    });
  }
});
