
function handleBlockFormatting(lineEl) {
  const text = lineEl.textContent;
  const section = lineEl.parentNode;
  console.log(lineEl.tagName)
  if (lineEl.tagName === 'P') {
    if (text === '```\u00A0' || text === '```  ' || text === '```\u00A0\u00A0') {
      console.log("inside code creation")
      const hexID = generateHexID();
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = createCodeBlock(hexID);
      const pre = tempDiv.firstElementChild;
      const code = pre.querySelector('code');
      const copyButton = pre.querySelector('i[data-copy-btn]');

      pre.id = `pre_${hexID}`;

      copyButton.addEventListener('click', (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(code.textContent);
        copyButton.classList.add('copied');
        setTimeout(() => copyButton.classList.remove('copied'), 1500);
      });

      section.replaceChild(pre, lineEl);
      const newP = createParagraph();
      section.appendChild(newP);

      placeCaretAtStart(code);
      return true;
    }

    else if (text === '---\u00A0\u00A0' || text === '***\u00A0\u00A0' || text === '___\u00A0\u00A0' || text === '---\u00A0\u00A0') {
      const hexID = generateHexID();
      const hr = document.createElement('hr');
      hr.id = `hr_${hexID}`;
      section.replaceChild(hr, lineEl);

      const newP = createParagraph();
      section.appendChild(newP);

      placeCaretAtStart(newP);
      return true;
    }

    else if (/^(?:\s|\u00A0)*#{1,6}(?:\s|\u00A0)+.*/.test(text)) {
      const hexID = generateHexID();
      const hashCount = (text.match(/#/g) || []).length;
      const content = text.replace(/^(?:\s|\u00A0)*#{1,6}(?:\s|\u00A0)*/, '').trim() || '\u00A0';
      
      if (hashCount === 1) {
        const newSection = document.createElement('section');
        const h1 = document.createElement('h1');
        h1.id = `heading_${hexID}`;
        
        if (content !== '\u00A0' && hasMarkdownPattern(content)) {
          processMarkdownInText(content, h1);
        } else {
          h1.textContent = content;
        }
        
        newSection.appendChild(h1);
        
        const currentSection = lineEl.closest('section');
        currentSection.parentNode.insertBefore(newSection, currentSection.nextSibling);
        
        lineEl.remove();
        
        const newP = createParagraph();
        newSection.appendChild(newP);
        
        placeCaretAtStart(newSection);
        return true;
      }
      
      const heading = document.createElement(`h${Math.min(hashCount, 6)}`);
      heading.id = `heading_${hexID}`;
      
      if (content !== '\u00A0' && hasMarkdownPattern(content)) {
        processMarkdownInText(content, heading);
      } else {
        heading.textContent = content;
      }

      section.replaceChild(heading, lineEl);
      const newP = createParagraph();
      section.appendChild(newP);

      placeCaretAtEnd(heading);
      return true;
    }

    const unorderedListMatch = text.match(/^[\*\-\+]\s(.*)/);
    const orderedListMatch = text.match(/^\d+\.\s(.*)/);

    if (unorderedListMatch || orderedListMatch) {
      const hexID = generateHexID();
      const isOrdered = !!orderedListMatch;
      const listType = isOrdered ? 'ol' : 'ul';
      const content = isOrdered ? orderedListMatch[1] : unorderedListMatch[1];

      const list = document.createElement(listType);
      list.id = `${listType}_${hexID}`;
      const li = document.createElement('li');
      li.id = `li_${generateHexID()}`;
      
      if (content && hasMarkdownPattern(content)) {
        processMarkdownInText(content, li);
      } else {
        li.textContent = content;
      }

      list.appendChild(li);
      section.replaceChild(list, lineEl);
      const newP = createParagraph();
      section.appendChild(newP);

      placeCaretAtEnd(li);
      return true;
    }

    const blockquoteMatch = text.match(/^>\s(.*)/);
    if (blockquoteMatch) {
      const hexID = generateHexID();
      const content = blockquoteMatch[1];
      const blockquote = document.createElement('blockquote');
      blockquote.id = `blockquote_${hexID}`;
      
      if (content && hasMarkdownPattern(content)) {
        processMarkdownInText(content, blockquote);
      } else {
        blockquote.textContent = content;
      }

      section.replaceChild(blockquote, lineEl);
      const newP = createParagraph();
      section.appendChild(newP);

      placeCaretAtEnd(blockquote);
      return true;
    }
  }

  return false;
}


const stylePatterns = [
  { regex: /\*\*(.+?)\*\*/g, tag: 'span', className: 'bold' },
  { regex: /(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, tag: 'span', className: 'italic' },
  { regex: /__(.+?)__/g, tag: 'span', className: 'underline' },
  { regex: /(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g, tag: 'span', className: 'italic' },
  { regex: /~~(.+?)~~/g, tag: 'span', className: 'strike' },
  { regex: /==(.+?)==/g, tag: 'span', className: 'mark' },
  { regex: /`([^`\n]+?)`/g, tag: 'span', className: 'code-inline' }
];

function hasMarkdownPattern(text) {
  const patterns = [
    /\*\*(.+?)\*\*/g,
    /(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g,
    /__(.+?)__/g,
    /(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g,
    /~~(.+?)~~/g,
    /==(.+?)==/g,
    /`([^`\n]+?)`/g
  ];
  return patterns.some(pattern => pattern.test(text));
}