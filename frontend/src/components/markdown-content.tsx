import Markdown from 'react-markdown'
import type { Components } from 'react-markdown'

import { cn } from '@/lib/utils'

type MarkdownContentProps = {
  markdown: string
  className?: string
}

const MARKDOWN_COMPONENTS: Components = {
  h1: ({ node: _node, className, ...props }) => (
    <h1 className={cn('mt-8 mb-4 font-sans text-2xl font-extrabold', className)} {...props} />
  ),
  h2: ({ node: _node, className, ...props }) => (
    <h2 className={cn('mt-8 mb-3 font-sans text-xl font-extrabold', className)} {...props} />
  ),
  h3: ({ node: _node, className, ...props }) => (
    <h3 className={cn('mt-6 mb-2 font-sans text-lg font-bold', className)} {...props} />
  ),
  p: ({ node: _node, className, ...props }) => (
    <p className={cn('my-4 text-base leading-7', className)} {...props} />
  ),
  strong: ({ node: _node, className, ...props }) => (
    <strong className={cn('font-bold', className)} {...props} />
  ),
  em: ({ node: _node, className, ...props }) => (
    <em className={cn('italic', className)} {...props} />
  ),
  ul: ({ node: _node, className, ...props }) => (
    <ul className={cn('my-4 list-disc pl-6 text-base leading-7', className)} {...props} />
  ),
  ol: ({ node: _node, className, ...props }) => (
    <ol className={cn('my-4 list-decimal pl-6 text-base leading-7', className)} {...props} />
  ),
  li: ({ node: _node, className, ...props }) => <li className={cn('my-1', className)} {...props} />,
  blockquote: ({ node: _node, className, ...props }) => (
    <blockquote
      className={cn('my-4 border-l-4 border-border pl-4 text-muted-foreground italic', className)}
      {...props}
    />
  ),
  a: ({ node: _node, className, ...props }) => (
    <a
      className={cn('text-primary-text underline underline-offset-2', className)}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  code: ({ node: _node, className, ...props }) => (
    <code
      className={cn('rounded-md bg-card px-1.5 py-0.5 font-mono text-sm', className)}
      {...props}
    />
  ),
  pre: ({ node: _node, className, ...props }) => (
    <pre
      className={cn(
        'my-4 overflow-x-auto rounded-xl border bg-card p-4 [&_code]:bg-transparent [&_code]:p-0',
        className,
      )}
      {...props}
    />
  ),
  hr: ({ node: _node, className, ...props }) => (
    <hr className={cn('my-8 border-border', className)} {...props} />
  ),
}

export function MarkdownContent({ markdown, className }: MarkdownContentProps) {
  return (
    <div className={cn('font-serif', className)}>
      <Markdown components={MARKDOWN_COMPONENTS}>{markdown}</Markdown>
    </div>
  )
}
