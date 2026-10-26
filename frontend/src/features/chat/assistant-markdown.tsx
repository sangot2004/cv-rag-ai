import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Render model text as Markdown without interpreting embedded HTML. */
export function AssistantMarkdown({content}: {content: string}) {
  return <div className="message-text assistant-markdown">
    <Markdown remarkPlugins={[remarkGfm]} skipHtml disallowedElements={["img"]}
      components={{
        h1: ({children}) => <h2>{children}</h2>,
        a: ({href, children, title}) => href
          ? <a href={href} title={title} target="_blank" rel="noopener noreferrer">{children}</a>
          : <span>{children}</span>,
        table: ({children}) => <div className="markdown-table-scroll" role="region" aria-label="Bảng trong câu trả lời" tabIndex={0}>
          <table>{children}</table>
        </div>,
      }}
    >{content}</Markdown>
  </div>;
}
