import { useRef } from 'react'
import Editor from '@monaco-editor/react'

export function MonacoEditor({ value, onChange, language = 'xml', theme = 'xmlforge-dark', readOnly = false }) {
  const editorRef = useRef(null)

  const handleMount = (editor, monaco) => {
    editorRef.current = editor

    // Define custom theme matching maquette #12151C bg, #0F1117 gutter
    monaco.editor.defineTheme('xmlforge-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'tag', foreground: '7CACFB', fontStyle: 'bold' },
        { token: 'attribute.name', foreground: '5EE29A' },
        { token: 'attribute.value', foreground: 'FFB86B' },
        { token: 'keyword', foreground: 'C792EA', fontStyle: 'bold' },
        { token: 'string', foreground: 'FFB86B' },
        { token: 'comment', foreground: '5B6472', fontStyle: 'italic' },
        { token: 'number', foreground: '5EE29A' },
        { token: 'type', foreground: 'FFB86B' },
      ],
      colors: {
        'editor.background': '#12151C',
        'editor.foreground': '#FFFFFF',
        'editorGutter.background': '#0F1117',
        'editorLineNumber.foreground': '#5B6472',
        'editorLineNumber.activeForeground': '#A0AEC0',
        'editor.lineHighlightBackground': '#1C212B',
        'editor.selectionBackground': '#3B82F630',
        'editorCursor.foreground': '#3B82F6',
        'editorIndentGuide.background': '#20252F',
        'editorIndentGuide.activeBackground': '#262C38',
      }
    })
    monaco.editor.setTheme('xmlforge-dark')
  }

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <Editor
        height="100%"
        language={language}
        value={value}
        onChange={onChange}
        onMount={handleMount}
        theme={theme}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 12,
          lineHeight: 21,
          wordWrap: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          lineNumbers: 'on',
          folding: true,
          foldingStrategy: 'indentation',
          showFoldingControls: 'always',
          matchBrackets: 'always',
          autoClosingBrackets: 'always',
          autoClosingQuotes: 'always',
          formatOnPaste: true,
          formatOnType: true,
          quickSuggestions: false,
          suggestOnTriggerCharacters: false,
          tabSize: 2,
          renderLineHighlight: 'line',
          overviewRulerBorder: false,
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          scrollbar: {
            verticalScrollbarSize: 10,
            horizontalScrollbarSize: 10,
            useShadows: false
          }
        }}
      />
    </div>
  )
}
