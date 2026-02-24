package com.claude.cameo.bridge.util;

import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.openapi.uml.SessionManager;
import com.google.gson.JsonObject;
import javax.swing.SwingUtilities;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Marshals model operations to the correct thread context.
 * <p>
 * Read operations run on the calling thread (Cameo model reads are thread-safe).
 * Write operations are dispatched to the Swing EDT and wrapped in a SessionManager
 * session so that they participate in undo/redo and do not corrupt the model.
 */
public class EdtDispatcher {
    private static final Logger LOG = Logger.getLogger(EdtDispatcher.class.getName());
    private static final long TIMEOUT_SECONDS = 30;

    /**
     * A model operation that receives the active Project and returns a result.
     */
    @FunctionalInterface
    public interface ModelAction<T> {
        T execute(Project project) throws Exception;
    }

    /**
     * Execute a read-only model action on the calling thread.
     *
     * @param action the action to execute
     * @param <T>    return type
     * @return the action result
     * @throws IllegalStateException if no project is open
     * @throws Exception             if the action throws
     */
    public static <T> T read(ModelAction<T> action) throws Exception {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            throw new IllegalStateException("No project is open");
        }
        return action.execute(project);
    }

    /**
     * Execute a model-write action on the Swing EDT inside a SessionManager session.
     * <p>
     * The session is committed on success and cancelled on failure, ensuring
     * model integrity. The caller blocks (up to {@link #TIMEOUT_SECONDS} seconds)
     * until the EDT completes the work.
     *
     * @param sessionName human-readable session name (shown in undo history)
     * @param action      the write action to execute
     * @return the JsonObject result produced by the action
     * @throws IllegalStateException if no project is open
     * @throws Exception             if the action throws or the EDT times out
     */
    public static JsonObject write(String sessionName, ModelAction<JsonObject> action) throws Exception {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            throw new IllegalStateException("No project is open");
        }

        CompletableFuture<JsonObject> future = new CompletableFuture<>();

        SwingUtilities.invokeLater(() -> {
            SessionManager sm = SessionManager.getInstance();
            boolean sessionCreated = false;
            try {
                sm.createSession(project, sessionName);
                sessionCreated = true;
                JsonObject result = action.execute(project);
                sm.closeSession(project);
                future.complete(result);
            } catch (Exception e) {
                if (sessionCreated) {
                    try {
                        sm.cancelSession(project);
                    } catch (Exception cancelEx) {
                        LOG.log(Level.WARNING,
                                "Failed to cancel session: " + sessionName, cancelEx);
                    }
                }
                LOG.log(Level.SEVERE, "Model write failed: " + sessionName, e);
                future.completeExceptionally(e);
            }
        });

        return future.get(TIMEOUT_SECONDS, TimeUnit.SECONDS);
    }
}
