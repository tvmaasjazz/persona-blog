import { FormSection } from '@/components/form/form-section'
import { withForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
import { blogPostFormOptions } from '@/features/blog-posts/blog-post-form-schema'
import { PublishingFields } from '@/features/blog-posts/components/publishing-fields'

// The blog post form's fields; the parent owns submitting.
export const BlogPostForm = withForm({
  ...blogPostFormOptions,
  props: {
    submitLabel: '',
    isPersonaPublic: false,
    onCancel: () => {},
  },
  render: function BlogPostFormRender({ form, submitLabel, isPersonaPublic, onCancel }) {
    return (
      <form
        noValidate
        className="flex flex-col gap-8"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        {/* Post */}
        <FormSection title="Post">
          <form.AppField name="title">{(field) => <field.TextField label="Title" />}</form.AppField>
          <form.AppField name="subtitle">
            {(field) => <field.TextField label="Subtitle" description="Optional." />}
          </form.AppField>
          <p className="text-sm text-muted-foreground">
            The body can't be edited yet. It stays as it is when you save.
          </p>
        </FormSection>

        {/* Publishing */}
        <FormSection title="Publishing">
          <PublishingFields form={form} fields="publishing" isPersonaPublic={isPersonaPublic} />
        </FormSection>

        {/* Buttons */}
        <div className="flex gap-3">
          <form.AppForm>
            <form.SubmitButton label={submitLabel} />
          </form.AppForm>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    )
  },
})
