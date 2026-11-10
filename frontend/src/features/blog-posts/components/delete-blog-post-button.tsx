import { Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { ConfirmActionButton } from '@/components/confirm-action-button'
import { useDeleteBlogPost } from '@/features/blog-posts/api/use-delete-blog-post'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type DeleteBlogPostButtonProps = {
  blogPostIdentity: string
  blogPostTitle: string
}

export function DeleteBlogPostButton({
  blogPostIdentity,
  blogPostTitle,
}: DeleteBlogPostButtonProps) {
  // Confirm, then delete and go to the list
  const navigate = useNavigate()
  const deleteBlogPost = useDeleteBlogPost()

  return (
    <ConfirmActionButton
      triggerLabel={
        <>
          <Trash2 aria-hidden />
          Delete
        </>
      }
      triggerVariant="ghost"
      triggerAriaLabel={`Delete ${blogPostTitle}`}
      title={`Delete ${blogPostTitle}?`}
      description="This post will be removed from your list. This can't be undone."
      actionLabel="Delete post"
      isPending={deleteBlogPost.isPending}
      onConfirm={() =>
        deleteBlogPost.mutate(blogPostIdentity, {
          onSuccess: () => {
            toast.success('Post deleted')
            navigate('/posts')
          },
          onError: (error) => {
            if (!isSessionEndedError(error)) {
              toast.error(apiErrorMessage(error))
            }
          },
        })
      }
    />
  )
}
