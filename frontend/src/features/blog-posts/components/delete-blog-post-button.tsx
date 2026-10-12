import { Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useDeleteBlogPost } from '@/features/blog-posts/api/use-delete-blog-post'
import { apiErrorMessage } from '@/lib/api-error'

type DeleteBlogPostButtonProps = {
  blogPostIdentity: string
  blogPostTitle: string
}

export function DeleteBlogPostButton({
  blogPostIdentity,
  blogPostTitle,
}: DeleteBlogPostButtonProps) {
  const navigate = useNavigate()
  const deleteBlogPost = useDeleteBlogPost()

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" aria-label={`Delete ${blogPostTitle}`}>
          <Trash2 aria-hidden />
          Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {blogPostTitle}?</AlertDialogTitle>
          <AlertDialogDescription>
            This post will be removed from your list. This can't be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={deleteBlogPost.isPending}
            onClick={(event) => {
              event.preventDefault()
              deleteBlogPost.mutate(blogPostIdentity, {
                onSuccess: () => {
                  toast.success('Post deleted')
                  navigate('/posts')
                },
                onError: (error) => toast.error(apiErrorMessage(error)),
              })
            }}
          >
            Delete post
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
